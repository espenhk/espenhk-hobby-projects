"""nl_to_logical_query's validation + one-repair-round-trip contract,
exercised against a stubbed Anthropic client so these run offline. The
live-API regression test lives in test_verified_answers.py."""

from __future__ import annotations

import pytest
from fjordroast.agent.nl_to_query import AgentError, nl_to_logical_query
from fjordroast.semantic.logical_query import LogicalQuery


class _FakeParseResponse:
    def __init__(self, parsed_output):
        self.parsed_output = parsed_output


class _FakeMessages:
    def __init__(self, outputs):
        self._outputs = list(outputs)
        self.calls = 0

    def parse(self, **kwargs):
        self.calls += 1
        output = self._outputs.pop(0)
        return _FakeParseResponse(output)


class _FakeClient:
    def __init__(self, outputs):
        self.messages = _FakeMessages(outputs)


def test_valid_first_try_needs_no_repair(semantic_model):
    good = LogicalQuery(metrics=["net_revenue"], group_by=["dim_store.city"])
    client = _FakeClient([good])

    result = nl_to_logical_query(client, semantic_model, "revenue by city")

    assert result == good
    assert client.messages.calls == 1


def test_repair_round_trip_recovers(semantic_model):
    bad = LogicalQuery(metrics=["net_revenue"], group_by=["dim_store.not_a_real_column"])
    good = LogicalQuery(metrics=["net_revenue"], group_by=["dim_store.city"])
    client = _FakeClient([bad, good])

    result = nl_to_logical_query(client, semantic_model, "revenue by city")

    assert result == good
    assert client.messages.calls == 2


def test_gives_up_after_one_failed_repair(semantic_model):
    bad = LogicalQuery(metrics=["net_revenue"], group_by=["dim_store.not_a_real_column"])
    still_bad = LogicalQuery(metrics=["also_not_real"])
    client = _FakeClient([bad, still_bad])

    with pytest.raises(AgentError):
        nl_to_logical_query(client, semantic_model, "revenue by city")

    assert client.messages.calls == 2
