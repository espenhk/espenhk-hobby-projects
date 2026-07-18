"""Regression tests over semantic_model/verified_answers.yml.

`test_verified_answers_compile_and_execute` runs offline (this is the same
check the `validate` CLI command performs) and is the CI gate. The live
variant asserts the real agent reproduces the same logical-query *shape* for
each canonical question — it requires network + ANTHROPIC_API_KEY and is
skipped otherwise, since this is a trust/regression check on real model
behavior, not something to fake with a stub.
"""

from __future__ import annotations

import os

import pytest

from fjordroast.agent.nl_to_query import nl_to_logical_query
from fjordroast.semantic.logical_query import LogicalQuery
from fjordroast.semantic.query_builder import execute_logical_query, validate_logical_query


def test_verified_answers_compile_and_execute(semantic_model, duck_con):
    assert semantic_model.verified_answers, "no verified answers loaded"
    for va in semantic_model.verified_answers:
        lq = LogicalQuery.model_validate(va.logical_query)
        errors = validate_logical_query(semantic_model, lq)
        assert errors == [], f"{va.question!r}: {errors}"
        df, _sql = execute_logical_query(duck_con, semantic_model, lq)
        assert len(df) > 0, f"{va.question!r} returned no rows"


@pytest.mark.skipif(not os.environ.get("ANTHROPIC_API_KEY"), reason="requires a live Anthropic API key")
@pytest.mark.parametrize(
    "index",
    range(4),
    ids=lambda i: f"verified_answer_{i}",
)
def test_agent_matches_verified_answer(semantic_model, index):
    import anthropic

    va = semantic_model.verified_answers[index]
    expected = LogicalQuery.model_validate(va.logical_query)

    client = anthropic.Anthropic()
    actual = nl_to_logical_query(client, semantic_model, va.question)

    assert set(actual.metrics) == set(expected.metrics)
    assert set(actual.group_by) == set(expected.group_by)
    expected_filter_fields = {f.field for f in expected.filters}
    actual_filter_fields = {f.field for f in actual.filters}
    assert expected_filter_fields <= actual_filter_fields
