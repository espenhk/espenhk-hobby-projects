"""Stretch goal: a minimal FastAPI chat endpoint + gallery of pinned
dashboards. `python cli.py serve` runs this."""

from __future__ import annotations

import html
import uuid
from pathlib import Path

import anthropic
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .agent.dashboard_spec import DashboardSpecError, generate_dashboard_specs
from .agent.narrative import generate_narrative_caption
from .agent.nl_to_query import AgentError, nl_to_logical_query
from .dashboard.render import title_from_question, write_dashboard
from .duck import get_connection
from .semantic.loader import load_semantic_model
from .semantic.logical_query import LogicalQuery
from .semantic.query_builder import execute_logical_query
from .store.persistence import DashboardStore

_GALLERY_PAGE = """\
<html><body style="font-family:sans-serif;max-width:760px;margin:2rem auto;">
<h1>Fjord Roast &mdash; conversational analytics</h1>
<h2>Pinned dashboards</h2>
<ul>{items}</ul>
<h2>Ask a question</h2>
<form onsubmit="ask(event)">
  <input id="q" style="width:70%" placeholder="e.g. revenue by city last quarter">
  <button>Ask</button>
</form>
<pre id="out"></pre>
<script>
async function ask(e) {{
  e.preventDefault();
  const q = document.getElementById('q').value;
  const r = await fetch('/api/ask', {{
    method: 'POST', headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify({{question: q}}),
  }});
  const j = await r.json();
  document.getElementById('out').textContent = JSON.stringify(j, null, 2);
  if (j.url) location.href = j.url;
}}
</script>
</body></html>
"""


class AskRequest(BaseModel):
    question: str
    identity: str | None = None


def build_app(project_root: Path) -> FastAPI:
    semantic_model_dir = project_root / "semantic_model"
    dashboards_dir = project_root / "dashboards"
    dashboards_dir.mkdir(exist_ok=True)

    store = DashboardStore(dashboards_dir / "dashboards.db")
    model = load_semantic_model(semantic_model_dir)
    client = anthropic.Anthropic()

    app = FastAPI(title="Fjord Roast Conversational Analytics")
    app.mount("/dashboards", StaticFiles(directory=dashboards_dir), name="dashboards")

    @app.get("/", response_class=HTMLResponse)
    def gallery():
        rows = store.list()
        items = "".join(
            f"<li><a href='/dashboards/{html.escape(Path(r.html_path).name)}'>{html.escape(r.question)}</a> "
            f"<small>({html.escape(r.created_at)})</small> &mdash; "
            f"<a href='/refresh/{html.escape(r.id)}'>refresh</a></li>"
            for r in rows
        ) or "<li><em>No dashboards yet &mdash; ask a question below.</em></li>"
        return _GALLERY_PAGE.format(items=items)

    @app.post("/api/ask")
    def ask(req: AskRequest):
        try:
            lq = nl_to_logical_query(client, model, req.question, identity=req.identity)
        except AgentError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        with get_connection() as con:
            df, sql = execute_logical_query(con, model, lq, identity=req.identity)

        try:
            specs = generate_dashboard_specs(client, req.question, df)
        except DashboardSpecError:
            specs = None

        try:
            narrative = generate_narrative_caption(client, req.question, df)
        except Exception:  # noqa: BLE001 - narrative is best-effort, never fatal
            narrative = ""

        record_id = uuid.uuid4().hex[:10]
        html_path = dashboards_dir / f"{record_id}.html"
        write_dashboard(
            html_path,
            title=title_from_question(req.question),
            question=req.question,
            df=df,
            specs=specs,
            narrative=narrative,
            sql=sql,
        )
        store.save(
            question=req.question,
            logical_query=lq.model_dump(exclude_none=True),
            sql=sql,
            vega_spec=specs,
            narrative=narrative,
            identity=req.identity,
            model_version=model.meta.version,
            anthropic_model=None,
            html_path=str(html_path),
            record_id=record_id,
        )
        return {"id": record_id, "url": f"/dashboards/{html_path.name}"}

    @app.get("/refresh/{record_id}")
    def refresh(record_id: str):
        record = store.get(record_id)
        if record is None:
            raise HTTPException(status_code=404, detail="No such dashboard")

        lq = LogicalQuery.model_validate(record.logical_query)
        with get_connection() as con:
            df, sql = execute_logical_query(con, model, lq, identity=record.identity)
        html_path = Path(record.html_path)
        write_dashboard(
            html_path,
            title=title_from_question(record.question),
            question=record.question,
            df=df,
            specs=record.vega_spec,
            narrative=record.narrative,
            sql=sql,
        )
        store.save(
            question=record.question,
            logical_query=record.logical_query,
            sql=sql,
            vega_spec=record.vega_spec,
            narrative=record.narrative,
            identity=record.identity,
            model_version=record.model_version,
            anthropic_model=record.anthropic_model,
            html_path=str(html_path),
            record_id=record.id,
        )
        return RedirectResponse(f"/dashboards/{html_path.name}")

    return app
