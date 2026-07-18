"""Loads /semantic_model/*.yml into a validated, in-memory SemanticModel.

This is the only place that reads the semantic-model files. Everything
downstream (grounding text, query compilation) works off the typed result,
never the raw YAML.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .schema import (
    ColumnDef,
    MetricDef,
    ModelMeta,
    Relationship,
    RowFilters,
    TableDef,
    VerifiedAnswer,
)

_FIELD_REF_RE_TEMPLATE = r"\b({tables})\.(\w+)\b"


class SemanticModelError(Exception):
    """Raised for referential-integrity failures in the semantic model files."""


@dataclass
class SemanticModel:
    project_root: Path
    meta: ModelMeta
    tables: dict[str, TableDef]
    relationships: list[Relationship]
    metrics: dict[str, MetricDef]
    row_filters: RowFilters
    verified_answers: list[VerifiedAnswer] = field(default_factory=list)

    # -- lookups -----------------------------------------------------------

    def get_table(self, name: str) -> TableDef:
        try:
            return self.tables[name]
        except KeyError as exc:
            raise SemanticModelError(f"Unknown table {name!r}") from exc

    def get_metric(self, name: str) -> MetricDef:
        try:
            return self.metrics[name]
        except KeyError as exc:
            raise SemanticModelError(f"Unknown metric {name!r}") from exc

    def relationship_to(self, table_name: str) -> Relationship:
        for rel in self.relationships:
            if rel.to_table == table_name:
                return rel
        raise SemanticModelError(f"No declared relationship to table {table_name!r}")

    def resolve_source_path(self, table_name: str) -> Path:
        table = self.get_table(table_name)
        return (self.project_root / table.source).resolve()

    def field_ref_pattern(self) -> re.Pattern:
        return re.compile(_FIELD_REF_RE_TEMPLATE.format(tables="|".join(re.escape(t) for t in self.tables)))

    def extract_field_refs(self, text: str) -> set[tuple[str, str]]:
        """Every 'table.column' token in `text` whose table is known."""
        return {(m.group(1), m.group(2)) for m in self.field_ref_pattern().finditer(text)}

    def resolve_column(self, field_ref: str) -> tuple[TableDef, ColumnDef]:
        if "." not in field_ref:
            raise SemanticModelError(f"Field {field_ref!r} must be 'table.column'")
        table_name, col_name = field_ref.split(".", 1)
        table = self.get_table(table_name)
        col = table.column(col_name)
        if col is None:
            raise SemanticModelError(f"Table {table_name!r} has no column {col_name!r}")
        return table, col


def _load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_semantic_model(semantic_model_dir: Path, project_root: Path | None = None) -> SemanticModel:
    semantic_model_dir = Path(semantic_model_dir)
    project_root = Path(project_root) if project_root else semantic_model_dir.parent

    model_yml = _load_yaml(semantic_model_dir / "model.yml")
    meta = ModelMeta.model_validate(model_yml)

    tables: dict[str, TableDef] = {}
    tables_dir = semantic_model_dir / "tables"
    for path in sorted(tables_dir.glob("*.yml")):
        t = TableDef.model_validate(_load_yaml(path))
        tables[t.name] = t

    rel_yml = _load_yaml(semantic_model_dir / "relationships.yml")
    relationships = [Relationship.model_validate(r) for r in rel_yml.get("relationships", [])]

    metrics: dict[str, MetricDef] = {}
    metrics_dir = semantic_model_dir / "metrics"
    for path in sorted(metrics_dir.glob("*.yml")):
        m = MetricDef.model_validate(_load_yaml(path))
        metrics[m.name] = m

    row_filters_path = semantic_model_dir / "access" / "row_filters.yml"
    row_filters = RowFilters.model_validate(_load_yaml(row_filters_path)) if row_filters_path.exists() else RowFilters()

    verified_path = semantic_model_dir / "verified_answers.yml"
    verified_answers: list[VerifiedAnswer] = []
    if verified_path.exists():
        va_yml = _load_yaml(verified_path)
        verified_answers = [VerifiedAnswer.model_validate(v) for v in va_yml.get("answers", [])]

    model = SemanticModel(
        project_root=project_root,
        meta=meta,
        tables=tables,
        relationships=relationships,
        metrics=metrics,
        row_filters=row_filters,
        verified_answers=verified_answers,
    )
    errors = validate_semantic_model(model)
    if errors:
        raise SemanticModelError("Semantic model failed validation:\n- " + "\n- ".join(errors))
    return model


def validate_semantic_model(model: SemanticModel) -> list[str]:
    """Referential-integrity assertions. Returns a list of human-readable
    error strings; empty means the model is internally consistent."""
    errors: list[str] = []

    if "fact_sales" not in model.tables:
        errors.append("No 'fact_sales' table declared.")

    # relationships reference real tables/columns, and connect to fact_sales
    for rel in model.relationships:
        if rel.from_table not in model.tables:
            errors.append(f"relationship {rel.name!r}: unknown from_table {rel.from_table!r}")
            continue
        if rel.to_table not in model.tables:
            errors.append(f"relationship {rel.name!r}: unknown to_table {rel.to_table!r}")
            continue
        if model.tables[rel.from_table].column(rel.from_column) is None:
            errors.append(f"relationship {rel.name!r}: {rel.from_table}.{rel.from_column} does not exist")
        if model.tables[rel.to_table].column(rel.to_column) is None:
            errors.append(f"relationship {rel.name!r}: {rel.to_table}.{rel.to_column} does not exist")

    joinable_tables = {"fact_sales"} | {rel.to_table for rel in model.relationships if rel.from_table == "fact_sales"}

    def _check_field_refs(context: str, text: str) -> None:
        for table_name, col_name in re.findall(r"\b(\w+)\.(\w+)\b", text):
            if table_name not in model.tables:
                continue  # not a field reference (e.g. a SQL function name.arg-like token) — ignore
            if table_name not in joinable_tables:
                errors.append(f"{context}: references table {table_name!r} which has no join to fact_sales")
            elif model.tables[table_name].column(col_name) is None:
                errors.append(f"{context}: {table_name}.{col_name} does not exist")

    # metrics: expressions/conditions reference real, joinable columns
    for metric in model.metrics.values():
        if metric.kind == "simple":
            if not metric.expression:
                errors.append(f"metric {metric.name!r}: kind=simple requires 'expression'")
            else:
                _check_field_refs(f"metric {metric.name!r} expression", metric.expression)
        elif metric.kind == "basket_ratio":
            if not metric.numerator_condition or not metric.denominator_condition:
                errors.append(f"metric {metric.name!r}: kind=basket_ratio requires numerator_condition and denominator_condition")
            else:
                _check_field_refs(f"metric {metric.name!r} numerator_condition", metric.numerator_condition)
                _check_field_refs(f"metric {metric.name!r} denominator_condition", metric.denominator_condition)

        for dim in metric.sliceable_dimensions:
            try:
                model.resolve_column(dim)
            except SemanticModelError as exc:
                errors.append(f"metric {metric.name!r} sliceable_dimensions: {exc}")
                continue
            table_name = dim.split(".", 1)[0]
            if table_name not in joinable_tables:
                errors.append(f"metric {metric.name!r} sliceable_dimensions: {dim} has no join to fact_sales")

    # row filters reference real, joinable columns
    for rf in model.row_filters.filters:
        _check_field_refs(f"row filter {rf.identity!r}", rf.predicate)

    # synonym collisions: the same synonym pointing at two different fields/metrics is ambiguous grounding
    errors.extend(_check_synonym_collisions(model))

    return errors


def _check_synonym_collisions(model: SemanticModel) -> list[str]:
    errors: list[str] = []
    synonym_owner: dict[str, str] = {}

    def _register(synonym: str, owner: str) -> None:
        key = synonym.strip().lower()
        if not key:
            return
        existing = synonym_owner.get(key)
        if existing and existing != owner:
            errors.append(f"synonym {synonym!r} is claimed by both {existing!r} and {owner!r}")
        else:
            synonym_owner[key] = owner

    # Only declared `synonyms` are checked for collisions — real column/metric
    # names are always disambiguated by their table prefix (or are unique
    # metric identifiers), so two tables legitimately sharing a physical key
    # name (e.g. every dim's own key vs. the matching FK in fact_sales) is
    # expected star-schema shape, not an ambiguity.
    for table in model.tables.values():
        for col in table.columns:
            owner = f"{table.name}.{col.name}"
            for syn in col.synonyms:
                _register(syn, owner)

    for metric in model.metrics.values():
        for syn in metric.synonyms:
            _register(syn, metric.name)

    return errors
