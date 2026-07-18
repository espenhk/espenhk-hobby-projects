"""Assembles a single self-contained dashboard.html with Jinja2: the
validated Vega-Lite spec(s) (or a table fallback), the data inlined as JSON,
vega/vega-lite/vega-embed from CDN, a title, the question, a "data as of"
line, and a short narrative caption.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from jinja2 import Environment, FileSystemLoader, select_autoescape

_TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
_ENV = Environment(loader=FileSystemLoader(_TEMPLATE_DIR), autoescape=select_autoescape(["html"]))

VEGA_VERSION = "6"
VEGA_LITE_VERSION = "6"
VEGA_EMBED_VERSION = "7"


def _json_for_script(obj) -> str:
    """json.dumps, with `</` escaped so embedded data can't prematurely close
    the surrounding <script> tag."""
    return json.dumps(obj, default=str).replace("</", "<\\/")


def render_dashboard_html(
    *,
    title: str,
    question: str,
    df: pd.DataFrame,
    specs: list[dict] | None,
    narrative: str,
    sql: str,
    created_at: datetime | None = None,
) -> str:
    template = _ENV.get_template("dashboard.html.j2")
    records = json.loads(df.to_json(orient="records", date_format="iso"))
    return template.render(
        title=title,
        question=question,
        narrative=narrative,
        sql=sql,
        specs_json=_json_for_script(specs) if specs else None,
        spec_count=len(specs) if specs else 0,
        table_columns=list(df.columns) if not specs else None,
        table_rows=records if not specs else None,
        data_json=_json_for_script(records),
        created_at=(created_at or datetime.now(timezone.utc)).strftime("%Y-%m-%d %H:%M UTC"),
        vega_version=VEGA_VERSION,
        vega_lite_version=VEGA_LITE_VERSION,
        vega_embed_version=VEGA_EMBED_VERSION,
    )


def write_dashboard(path: Path, **kwargs) -> Path:
    html = render_dashboard_html(**kwargs)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")
    return path


def title_from_question(question: str) -> str:
    q = question.strip().rstrip("?")
    return (q[0].upper() + q[1:]) if q else "Fjord Roast Dashboard"
