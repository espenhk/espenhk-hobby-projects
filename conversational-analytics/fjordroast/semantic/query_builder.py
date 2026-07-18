"""Compiles a validated LogicalQuery into DuckDB SQL.

This is the only place SQL gets written. Metrics expand to their declared
expressions here — never in the LLM's output — which is what makes the
numbers trustworthy regardless of what the agent produced upstream.
"""

from __future__ import annotations

from dataclasses import dataclass

import duckdb
import pandas as pd

from .loader import SemanticModel
from .logical_query import Filter, LogicalQuery
from .schema import MetricDef

DEFAULT_LIMIT = 1000
_TIME_GRAINS = {"week", "month", "quarter", "year"}


class QueryCompileError(Exception):
    """Raised when a LogicalQuery fails validation against the semantic model."""


# --------------------------------------------------------------------------
# validation
# --------------------------------------------------------------------------


def validate_logical_query(model: SemanticModel, lq: LogicalQuery) -> list[str]:
    """Every referenced metric/dimension/field must exist in the model.
    Returns a list of error strings; empty means the query is compilable."""
    errors: list[str] = []

    metric_defs: list[MetricDef] = []
    for name in lq.metrics:
        if name not in model.metrics:
            errors.append(f"Unknown metric {name!r}. Known metrics: {', '.join(sorted(model.metrics))}")
        else:
            metric_defs.append(model.metrics[name])

    allowed_dims: set[str] = set()
    for m in metric_defs:
        allowed_dims.update(m.sliceable_dimensions)

    for dim in lq.group_by:
        try:
            table, col = model.resolve_column(dim)
        except Exception as exc:  # noqa: BLE001 - surfaced as a validation error string
            errors.append(str(exc))
            continue
        if col.hidden_from_ai:
            errors.append(f"group_by field {dim!r} is hidden_from_ai and cannot be used")
        elif metric_defs and dim not in allowed_dims:
            errors.append(f"group_by field {dim!r} is not sliceable for metric(s) {', '.join(lq.metrics)}")

    for filt in lq.filters:
        try:
            _table, col = model.resolve_column(filt.field)
        except Exception as exc:  # noqa: BLE001
            errors.append(str(exc))
            continue
        if col.hidden_from_ai:
            errors.append(f"filter field {filt.field!r} is hidden_from_ai and cannot be used")
        if filt.op in ("in", "not in") and not isinstance(filt.value, list):
            errors.append(f"filter on {filt.field!r} with op {filt.op!r} requires a list value")
        if filt.op == "between" and (not isinstance(filt.value, list) or len(filt.value) != 2):
            errors.append(f"filter on {filt.field!r} with op 'between' requires a 2-item list value")

    if lq.time_grain and "dim_date.date" not in lq.group_by:
        errors.append("time_grain is set but 'dim_date.date' is not in group_by")

    valid_sort_targets = set(lq.metrics) | {_dim_alias_hint(d) for d in lq.group_by}
    for s in lq.sort:
        if s.field not in valid_sort_targets and s.field not in lq.group_by:
            errors.append(f"sort field {s.field!r} is not a requested metric or group_by field")

    return errors


def _dim_alias_hint(field: str) -> str:
    return field.split(".", 1)[1] if "." in field else field


# --------------------------------------------------------------------------
# compilation
# --------------------------------------------------------------------------


@dataclass
class DimSpec:
    field: str
    expr: str
    alias: str


def _unique_alias(base: str, used: set[str]) -> str:
    alias = base
    n = 2
    while alias in used:
        alias = f"{base}_{n}"
        n += 1
    used.add(alias)
    return alias


def _dim_specs(model: SemanticModel, lq: LogicalQuery) -> list[DimSpec]:
    used: set[str] = set()
    specs: list[DimSpec] = []
    for field in lq.group_by:
        table, col = model.resolve_column(field)
        if field == "dim_date.date" and lq.time_grain and lq.time_grain in _TIME_GRAINS:
            expr = f"DATE_TRUNC('{lq.time_grain}', dim_date.date)"
        else:
            expr = f"{table.name}.{col.name}"
        alias = _unique_alias(col.name, used)
        specs.append(DimSpec(field=field, expr=expr, alias=alias))
    return specs


def _quote_literal(value: object) -> str:
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float)):
        return repr(value)
    return "'" + str(value).replace("'", "''") + "'"


def _column_sql_type(model: SemanticModel, field: str) -> str:
    _table, col = model.resolve_column(field)
    return {"string": "VARCHAR", "integer": "BIGINT", "float": "DOUBLE", "date": "DATE", "boolean": "BOOLEAN"}[
        col.type
    ]


def _compile_filter(model: SemanticModel, filt: Filter, params: list) -> str:
    table, col = model.resolve_column(filt.field)
    field_sql = f"{table.name}.{col.name}"
    sql_type = _column_sql_type(model, filt.field)

    def placeholder() -> str:
        return f"CAST(? AS {sql_type})"

    if filt.op in ("=", "!=", ">", ">=", "<", "<="):
        params.append(filt.value)
        return f"{field_sql} {filt.op} {placeholder()}"
    if filt.op in ("in", "not in"):
        values = filt.value if isinstance(filt.value, list) else [filt.value]
        params.extend(values)
        placeholders = ", ".join(placeholder() for _ in values)
        keyword = "IN" if filt.op == "in" else "NOT IN"
        return f"{field_sql} {keyword} ({placeholders})"
    if filt.op == "between":
        lo, hi = filt.value
        params.extend([lo, hi])
        return f"{field_sql} BETWEEN {placeholder()} AND {placeholder()}"
    raise QueryCompileError(f"Unsupported filter op {filt.op!r}")


def _required_tables(model: SemanticModel, lq: LogicalQuery, extra_refs: list[tuple[str, str]]) -> set[str]:
    tables: set[str] = set()
    for field in lq.group_by:
        tables.add(field.split(".", 1)[0])
    for filt in lq.filters:
        tables.add(filt.field.split(".", 1)[0])
    for t, _c in extra_refs:
        tables.add(t)
    tables.discard("fact_sales")
    return tables


def _from_join_sql(model: SemanticModel, tables: set[str]) -> str:
    fact = model.get_table("fact_sales")
    lines = [f"read_parquet('{model.resolve_source_path('fact_sales')}') AS fact_sales"]
    for table_name in sorted(tables):
        rel = model.relationship_to(table_name)
        source = model.resolve_source_path(table_name)
        lines.append(
            f"LEFT JOIN read_parquet('{source}') AS {table_name} "
            f"ON fact_sales.{rel.from_column} = {table_name}.{rel.to_column}"
        )
    return "\n".join(lines)


def _where_sql(model: SemanticModel, lq: LogicalQuery, identity: str | None, params: list) -> str:
    clauses = [_compile_filter(model, f, params) for f in lq.filters]
    if identity is not None:
        predicate = model.row_filters.predicate_for(identity)
        if predicate:
            clauses.append(f"({predicate})")
    return " AND ".join(clauses) if clauses else "1=1"


def compile_logical_query(
    model: SemanticModel, lq: LogicalQuery, identity: str | None = None
) -> tuple[str, list]:
    errors = validate_logical_query(model, lq)
    if errors:
        raise QueryCompileError("; ".join(errors))

    metric_defs = {name: model.get_metric(name) for name in lq.metrics}
    simple_metrics = {n: m for n, m in metric_defs.items() if m.kind == "simple"}
    ratio_metrics = {n: m for n, m in metric_defs.items() if m.kind == "basket_ratio"}

    metric_field_refs: list[tuple[str, str]] = []
    for m in metric_defs.values():
        texts = [m.expression] if m.kind == "simple" else [m.numerator_condition, m.denominator_condition]
        for text in texts:
            if text:
                metric_field_refs.extend(model.extract_field_refs(text))

    tables = _required_tables(model, lq, metric_field_refs)
    if identity is not None:
        predicate = model.row_filters.predicate_for(identity)
        if predicate:
            tables |= {t for t, _c in model.extract_field_refs(predicate)} - {"fact_sales"}

    dim_specs = _dim_specs(model, lq)
    dim_select = ", ".join(f"{d.expr} AS {d.alias}" for d in dim_specs)
    dim_group_by = ", ".join(d.expr for d in dim_specs)
    dim_alias_list = ", ".join(d.alias for d in dim_specs)

    params: list = []
    from_join = _from_join_sql(model, tables)
    where_sql = _where_sql(model, lq, identity, params)

    order_sql = _order_by_sql(lq, dim_specs)
    limit_sql = f"LIMIT {lq.limit or DEFAULT_LIMIT}"

    if not ratio_metrics:
        select_parts = ([dim_select] if dim_select else []) + [
            f"{m.expression} AS {name}" for name, m in simple_metrics.items()
        ]
        sql = f"SELECT {', '.join(select_parts)}\nFROM {from_join}\nWHERE {where_sql}"
        if dim_group_by:
            sql += f"\nGROUP BY {dim_group_by}"
        sql += f"\n{order_sql}\n{limit_sql}"
        return sql, params

    # -- queries touching a basket_ratio metric need a two-level aggregation:
    # first collapse to one row per basket (+ dims), then aggregate ratios.
    basket_flags = []
    for name, m in ratio_metrics.items():
        basket_flags.append(f"MAX(CASE WHEN {m.numerator_condition} THEN 1 ELSE 0 END) AS {name}_num")
        basket_flags.append(f"MAX(CASE WHEN {m.denominator_condition} THEN 1 ELSE 0 END) AS {name}_den")

    basket_select = ", ".join(["fact_sales.receipt_id AS receipt_id"] + ([dim_select] if dim_select else []) + basket_flags)
    basket_group_by = ", ".join(["fact_sales.receipt_id"] + ([dim_group_by] if dim_group_by else []))

    ratio_exprs = ", ".join(
        f"SUM({name}_num * {name}_den)::DOUBLE / NULLIF(SUM({name}_den), 0) AS {name}" for name in ratio_metrics
    )
    ratio_select = ", ".join(([dim_alias_list] if dim_alias_list else []) + [ratio_exprs])
    ratio_group_by = dim_alias_list

    ctes = [
        f"basket_level AS (\n  SELECT {basket_select}\n  FROM {from_join}\n  WHERE {where_sql}\n  GROUP BY {basket_group_by}\n)",
        "ratio_agg AS (\n  SELECT "
        + ratio_select
        + "\n  FROM basket_level"
        + (f"\n  GROUP BY {ratio_group_by}" if ratio_group_by else "")
        + "\n)",
    ]

    if simple_metrics:
        simple_select_parts = ([dim_select] if dim_select else []) + [
            f"{m.expression} AS {name}" for name, m in simple_metrics.items()
        ]
        simple_sql = f"SELECT {', '.join(simple_select_parts)}\n  FROM {from_join}\n  WHERE {where_sql}"
        if dim_group_by:
            simple_sql += f"\n  GROUP BY {dim_group_by}"
        ctes.insert(0, f"simple_agg AS (\n  {simple_sql}\n)")

        if dim_alias_list:
            join_cond = " AND ".join(f"simple_agg.{d.alias} = ratio_agg.{d.alias}" for d in dim_specs)
            coalesced_dims = ", ".join(f"COALESCE(simple_agg.{d.alias}, ratio_agg.{d.alias}) AS {d.alias}" for d in dim_specs)
            final_select = ", ".join(
                ([coalesced_dims] if coalesced_dims else [])
                + [f"simple_agg.{n}" for n in simple_metrics]
                + [f"ratio_agg.{n}" for n in ratio_metrics]
            )
            final_from = f"simple_agg FULL OUTER JOIN ratio_agg ON {join_cond}"
        else:
            final_select = ", ".join([f"simple_agg.{n}" for n in simple_metrics] + [f"ratio_agg.{n}" for n in ratio_metrics])
            final_from = "simple_agg CROSS JOIN ratio_agg"
    else:
        final_select = ", ".join(([dim_alias_list] if dim_alias_list else []) + list(ratio_metrics))
        final_from = "ratio_agg"

    sql = "WITH " + ",\n".join(ctes) + f"\nSELECT {final_select}\nFROM {final_from}\n{order_sql}\n{limit_sql}"
    return sql, params


def _order_by_sql(lq: LogicalQuery, dim_specs: list[DimSpec]) -> str:
    if lq.sort:
        parts = []
        for s in lq.sort:
            alias = s.field if "." not in s.field else _dim_alias_hint(s.field)
            parts.append(f"{alias} {s.direction.upper()}")
        return "ORDER BY " + ", ".join(parts)
    if dim_specs:
        return "ORDER BY " + ", ".join(d.alias for d in dim_specs)
    return ""


# --------------------------------------------------------------------------
# execution
# --------------------------------------------------------------------------


def execute_logical_query(
    con: duckdb.DuckDBPyConnection, model: SemanticModel, lq: LogicalQuery, identity: str | None = None
) -> tuple[pd.DataFrame, str]:
    sql, params = compile_logical_query(model, lq, identity=identity)
    df = con.execute(sql, params).df()
    return df, sql
