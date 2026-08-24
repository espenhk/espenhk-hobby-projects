"""Compiles LogicalQuery -> DuckDB SQL and executes against the shipped
Fjord Roast data. This is the layer that guarantees the LLM never touches a
number: every value below comes from DuckDB, not from a mocked agent."""

from __future__ import annotations

import pytest
from fjordroast.semantic.logical_query import Filter, LogicalQuery, SortSpec
from fjordroast.semantic.query_builder import (
    QueryCompileError,
    execute_logical_query,
    validate_logical_query,
)


def test_simple_metric_no_group_by(semantic_model, duck_con):
    lq = LogicalQuery(metrics=["net_revenue"])
    df, sql = execute_logical_query(duck_con, semantic_model, lq)
    assert len(df) == 1
    assert df["net_revenue"].iloc[0] > 0
    assert "GROUP BY" not in sql


def test_group_by_dimension(semantic_model, duck_con):
    lq = LogicalQuery(metrics=["net_revenue"], group_by=["dim_store.city"])
    df, sql = execute_logical_query(duck_con, semantic_model, lq)
    assert set(df["city"]) == {"Tromsø", "Bergen", "Oslo", "Trondheim"}
    assert df["net_revenue"].sum() > 0


def test_time_grain_truncation(semantic_model, duck_con):
    lq = LogicalQuery(metrics=["net_revenue"], group_by=["dim_date.date"], time_grain="month")
    df, sql = execute_logical_query(duck_con, semantic_model, lq)
    assert "DATE_TRUNC('month'" in sql
    assert len(df) <= 24  # 2 years of data


def test_filter_equality(semantic_model, duck_con):
    lq = LogicalQuery(
        metrics=["units_sold"],
        filters=[Filter(field="dim_product.category", op="=", value="Coffee")],
    )
    df, _sql = execute_logical_query(duck_con, semantic_model, lq)
    assert df["units_sold"].iloc[0] > 0


def test_filter_in_list(semantic_model, duck_con):
    lq = LogicalQuery(
        metrics=["net_revenue"],
        group_by=["dim_store.city"],
        filters=[Filter(field="dim_store.city", op="in", value=["Oslo", "Bergen"])],
    )
    df, _sql = execute_logical_query(duck_con, semantic_model, lq)
    assert set(df["city"]) == {"Oslo", "Bergen"}


def test_ratio_metric_alone(semantic_model, duck_con):
    lq = LogicalQuery(metrics=["food_attach_rate"], group_by=["dim_store.city"])
    df, _sql = execute_logical_query(duck_con, semantic_model, lq)
    assert (df["food_attach_rate"].between(0, 1)).all()


def test_ratio_metric_combined_with_simple_metric(semantic_model, duck_con):
    lq = LogicalQuery(
        metrics=["avg_basket_value", "food_attach_rate"],
        group_by=["dim_store.store_name"],
    )
    df, _sql = execute_logical_query(duck_con, semantic_model, lq)
    assert len(df) == 6  # six cafés
    assert (df["avg_basket_value"] > 0).all()
    assert (df["food_attach_rate"].between(0, 1)).all()


def test_row_filter_restricts_results(semantic_model, duck_con):
    lq = LogicalQuery(metrics=["net_revenue"], group_by=["dim_store.city"])
    df, _sql = execute_logical_query(duck_con, semantic_model, lq, identity="manager_bergen")
    assert set(df["city"]) == {"Bergen"}


def test_row_filter_single_store(semantic_model, duck_con):
    lq = LogicalQuery(metrics=["net_revenue"], group_by=["dim_store.store_name"])
    df, _sql = execute_logical_query(duck_con, semantic_model, lq, identity="manager_oslo_sentrum")
    assert set(df["store_name"]) == {"Oslo Sentrum"}


def test_sort_and_limit(semantic_model, duck_con):
    lq = LogicalQuery(
        metrics=["net_revenue"],
        group_by=["dim_product.name"],
        sort=[SortSpec(field="net_revenue", direction="desc")],
        limit=3,
    )
    df, _sql = execute_logical_query(duck_con, semantic_model, lq)
    assert len(df) == 3
    assert list(df["net_revenue"]) == sorted(df["net_revenue"], reverse=True)


# -- validation ---------------------------------------------------------


def test_rejects_unknown_metric(semantic_model):
    lq = LogicalQuery(metrics=["not_a_real_metric"])
    errors = validate_logical_query(semantic_model, lq)
    assert any("not_a_real_metric" in e for e in errors)


def test_rejects_unknown_dimension(semantic_model):
    lq = LogicalQuery(metrics=["net_revenue"], group_by=["dim_store.not_a_column"])
    errors = validate_logical_query(semantic_model, lq)
    assert errors


def test_rejects_hidden_field(semantic_model):
    lq = LogicalQuery(metrics=["net_revenue"], group_by=["dim_store.store_id"])
    errors = validate_logical_query(semantic_model, lq)
    assert any("hidden_from_ai" in e for e in errors)


def test_rejects_dimension_not_sliceable_for_metric(semantic_model):
    # gross_margin does not declare dim_member.loyalty_tier as sliceable
    lq = LogicalQuery(metrics=["gross_margin"], group_by=["dim_member.loyalty_tier"])
    errors = validate_logical_query(semantic_model, lq)
    assert errors


def test_compile_raises_on_invalid_query(semantic_model):
    lq = LogicalQuery(metrics=["not_a_real_metric"])
    with pytest.raises(QueryCompileError):
        execute_logical_query(None, semantic_model, lq)  # type: ignore[arg-type]
