"""Validation logic for agent-produced Vega-Lite specs: schema validation
against the pinned Vega-Lite v6 schema, plus the field whitelist that
guarantees the chart never references a column that isn't in the result."""

from __future__ import annotations

import pandas as pd
from fjordroast.agent.dashboard_spec import _extract_json, validate_specs

COLUMNS = ["city", "net_revenue"]


def _sample_df() -> pd.DataFrame:
    return pd.DataFrame({"city": ["Oslo", "Bergen"], "net_revenue": [100.0, 200.0]})


def test_valid_bar_spec_passes():
    spec = {
        "$schema": "https://vega.github.io/schema/vega-lite/v6.json",
        "title": "Revenue by city",
        "mark": "bar",
        "data": {"name": "table"},
        "encoding": {
            "x": {"field": "city", "type": "nominal"},
            "y": {"field": "net_revenue", "type": "quantitative"},
            "tooltip": [{"field": "city", "type": "nominal"}, {"field": "net_revenue", "type": "quantitative"}],
        },
    }
    assert validate_specs([spec], COLUMNS) == []


def test_unknown_field_is_rejected():
    spec = {
        "mark": "bar",
        "data": {"name": "table"},
        "encoding": {
            "x": {"field": "not_a_real_column", "type": "nominal"},
            "y": {"field": "net_revenue", "type": "quantitative"},
        },
    }
    errors = validate_specs([spec], COLUMNS)
    assert any("not_a_real_column" in e for e in errors)


def test_wrong_data_binding_is_rejected():
    spec = {
        "mark": "bar",
        "data": {"values": [{"city": "Oslo", "net_revenue": 1}]},
        "encoding": {
            "x": {"field": "city", "type": "nominal"},
            "y": {"field": "net_revenue", "type": "quantitative"},
        },
    }
    errors = validate_specs([spec], COLUMNS)
    assert any("data" in e for e in errors)


def test_schema_invalid_mark_is_rejected():
    spec = {
        "mark": "not_a_real_mark_type",
        "data": {"name": "table"},
        "encoding": {"x": {"field": "city", "type": "nominal"}},
    }
    errors = validate_specs([spec], COLUMNS)
    assert errors


def test_extract_json_handles_markdown_fence():
    text = '```json\n{"mark": "bar"}\n```'
    assert _extract_json(text) == {"mark": "bar"}


def test_extract_json_handles_raw_json():
    text = '{"mark": "bar"}'
    assert _extract_json(text) == {"mark": "bar"}


def test_derived_field_from_transform_is_allowed():
    spec = {
        "mark": "text",
        "data": {"name": "table"},
        "transform": [{"aggregate": [{"op": "sum", "field": "net_revenue", "as": "total_revenue"}]}],
        "encoding": {"text": {"field": "total_revenue", "type": "quantitative"}},
    }
    assert validate_specs([spec], COLUMNS) == []


def test_field_not_produced_by_any_transform_is_still_rejected():
    spec = {
        "mark": "text",
        "data": {"name": "table"},
        "transform": [{"aggregate": [{"op": "sum", "field": "net_revenue", "as": "total_revenue"}]}],
        "encoding": {"text": {"field": "made_up_field", "type": "quantitative"}},
    }
    errors = validate_specs([spec], COLUMNS)
    assert any("made_up_field" in e for e in errors)
