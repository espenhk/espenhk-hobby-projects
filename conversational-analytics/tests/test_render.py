from __future__ import annotations

import pandas as pd
from fjordroast.dashboard.render import render_dashboard_html, title_from_question


def test_render_with_specs_embeds_data_and_vegaembed():
    df = pd.DataFrame({"city": ["Oslo", "Bergen"], "net_revenue": [100.0, 200.0]})
    html = render_dashboard_html(
        title="Revenue by city",
        question="What is revenue by city?",
        df=df,
        specs=[{"mark": "bar", "data": {"name": "table"}}],
        narrative="Bergen leads on revenue.",
        sql="SELECT city, net_revenue FROM ...",
    )
    assert "vega-embed" in html
    assert "Bergen leads on revenue." in html
    assert "vis-0" in html
    assert '"net_revenue":100.0' in html or '"net_revenue": 100.0' in html


def test_render_without_specs_falls_back_to_table():
    df = pd.DataFrame({"city": ["Oslo"], "net_revenue": [100.0]})
    html = render_dashboard_html(
        title="Revenue by city",
        question="What is revenue by city?",
        df=df,
        specs=None,
        narrative="Table fallback.",
        sql="SELECT 1",
    )
    assert "<table>" in html
    assert "<th>city</th>" in html


def test_title_from_question():
    assert title_from_question("how did revenue trend?") == "How did revenue trend"
    assert title_from_question("") == "Fjord Roast Dashboard"
