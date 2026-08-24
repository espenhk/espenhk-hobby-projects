"""Loader + referential-integrity tests — the `validate` CLI command's
underlying logic. If someone typos a column name in a metric expression or a
sliceable_dimensions entry, this is what catches it."""

from __future__ import annotations

import shutil

import pytest
import yaml
from fjordroast.semantic.loader import (
    SemanticModelError,
    load_semantic_model,
    validate_semantic_model,
)
from tests.conftest import SEMANTIC_MODEL_DIR


def test_loads_real_semantic_model(semantic_model):
    assert semantic_model.meta.name == "Fjord Roast Sales"
    assert set(semantic_model.tables) == {"fact_sales", "dim_product", "dim_store", "dim_date", "dim_member"}
    assert "net_revenue" in semantic_model.metrics
    assert len(semantic_model.relationships) == 4


def test_real_model_has_no_validation_errors(semantic_model):
    errors = validate_semantic_model(semantic_model)
    assert errors == []


def test_verified_answers_loaded(semantic_model):
    assert len(semantic_model.verified_answers) >= 4
    questions = {va.question for va in semantic_model.verified_answers}
    assert "What is net revenue by city in 2025?" in questions


def test_row_filters_loaded(semantic_model):
    assert semantic_model.row_filters.predicate_for("hq_admin") == "1=1"
    assert "Bergen" in semantic_model.row_filters.predicate_for("manager_bergen")
    with pytest.raises(KeyError):
        semantic_model.row_filters.predicate_for("no_such_identity")


def test_catches_bad_relationship_column(tmp_path):
    broken_dir = tmp_path / "semantic_model"
    shutil.copytree(SEMANTIC_MODEL_DIR, broken_dir)

    rel_path = broken_dir / "relationships.yml"
    rels = yaml.safe_load(rel_path.read_text())
    rels["relationships"][0]["to_column"] = "not_a_real_column"
    rel_path.write_text(yaml.safe_dump(rels))

    with pytest.raises(SemanticModelError, match="not_a_real_column"):
        load_semantic_model(broken_dir)


def test_catches_metric_referencing_missing_column(tmp_path):
    broken_dir = tmp_path / "semantic_model"
    shutil.copytree(SEMANTIC_MODEL_DIR, broken_dir)

    metric_path = broken_dir / "metrics" / "net_revenue.yml"
    metric = yaml.safe_load(metric_path.read_text())
    metric["expression"] = "SUM(fact_sales.not_a_real_column)"
    metric_path.write_text(yaml.safe_dump(metric))

    with pytest.raises(SemanticModelError, match="not_a_real_column"):
        load_semantic_model(broken_dir)


def test_catches_ambiguous_synonym(tmp_path):
    broken_dir = tmp_path / "semantic_model"
    shutil.copytree(SEMANTIC_MODEL_DIR, broken_dir)

    metric_path = broken_dir / "metrics" / "units_sold.yml"
    metric = yaml.safe_load(metric_path.read_text())
    # "revenue" is already a synonym of net_revenue — claiming it for units_sold is ambiguous.
    metric["synonyms"].append("revenue")
    metric_path.write_text(yaml.safe_dump(metric))

    with pytest.raises(SemanticModelError, match="revenue"):
        load_semantic_model(broken_dir)
