from __future__ import annotations

from fjordroast.store.persistence import DashboardStore


def test_save_and_get_roundtrip(tmp_path):
    store = DashboardStore(tmp_path / "dashboards.db")
    record = store.save(
        question="revenue by city",
        logical_query={"metrics": ["net_revenue"], "group_by": ["dim_store.city"]},
        sql="SELECT 1",
        vega_spec=[{"mark": "bar"}],
        narrative="Bergen leads.",
        identity=None,
        model_version="1.0",
        anthropic_model="claude-opus-4-8",
        html_path=str(tmp_path / "abc123.html"),
        record_id="abc123",
    )
    assert record.id == "abc123"

    fetched = store.get("abc123")
    assert fetched is not None
    assert fetched.question == "revenue by city"
    assert fetched.logical_query == {"metrics": ["net_revenue"], "group_by": ["dim_store.city"]}
    assert fetched.vega_spec == [{"mark": "bar"}]

    store.close()


def test_list_orders_newest_first(tmp_path):
    store = DashboardStore(tmp_path / "dashboards.db")
    store.save(
        question="q1", logical_query={"metrics": ["net_revenue"]}, sql="SELECT 1", vega_spec=None,
        narrative="", identity=None, model_version="1.0", anthropic_model=None,
        html_path="a.html", record_id="a",
    )
    store.save(
        question="q2", logical_query={"metrics": ["net_revenue"]}, sql="SELECT 1", vega_spec=None,
        narrative="", identity=None, model_version="1.0", anthropic_model=None,
        html_path="b.html", record_id="b",
    )
    ids = [r.id for r in store.list()]
    assert set(ids) == {"a", "b"}
    store.close()


def test_get_missing_returns_none(tmp_path):
    store = DashboardStore(tmp_path / "dashboards.db")
    assert store.get("nope") is None
    store.close()
