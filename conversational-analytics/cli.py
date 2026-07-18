#!/usr/bin/env python3
"""Fjord Roast conversational analytics CLI.

    python cli.py ask "How did cold drink sales trend last summer?"
    python cli.py validate
    python cli.py refresh <id>
    python cli.py serve          # stretch: FastAPI chat + gallery

Requires ANTHROPIC_API_KEY for `ask` and `serve`; `validate` and `refresh`
run entirely offline against the shipped Parquet data.
"""

from __future__ import annotations

import argparse
import os
import sys
import uuid
import webbrowser
from pathlib import Path

from fjordroast.dashboard.render import title_from_question, write_dashboard
from fjordroast.duck import get_connection
from fjordroast.semantic.loader import SemanticModelError, load_semantic_model
from fjordroast.semantic.logical_query import LogicalQuery
from fjordroast.semantic.query_builder import execute_logical_query, validate_logical_query
from fjordroast.store.persistence import DashboardStore

PROJECT_ROOT = Path(__file__).resolve().parent
SEMANTIC_MODEL_DIR = PROJECT_ROOT / "semantic_model"
DASHBOARDS_DIR = PROJECT_ROOT / "dashboards"
STORE_PATH = DASHBOARDS_DIR / "dashboards.db"

DEFAULT_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-opus-4-8")


def cmd_validate(args: argparse.Namespace) -> int:
    try:
        model = load_semantic_model(SEMANTIC_MODEL_DIR)
    except SemanticModelError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1

    print(
        f"OK: semantic model {model.meta.name!r} v{model.meta.version} — "
        f"{len(model.tables)} tables, {len(model.metrics)} metrics, "
        f"{len(model.relationships)} relationships, {len(model.verified_answers)} verified answers."
    )

    con = get_connection()
    failures: list[str] = []
    for va in model.verified_answers:
        try:
            lq = LogicalQuery.model_validate(va.logical_query)
        except Exception as exc:  # noqa: BLE001
            failures.append(f"{va.question!r}: invalid logical query shape: {exc}")
            continue
        errors = validate_logical_query(model, lq)
        if errors:
            failures.append(f"{va.question!r}: {errors}")
            continue
        try:
            execute_logical_query(con, model, lq)
        except Exception as exc:  # noqa: BLE001
            failures.append(f"{va.question!r}: failed to execute: {exc}")

    if failures:
        print(f"FAIL: {len(failures)}/{len(model.verified_answers)} verified_answers.yml queries failed:")
        for f in failures:
            print(f"  - {f}")
        return 1

    print(f"OK: all {len(model.verified_answers)} verified_answers.yml queries compile and execute.")
    return 0


def cmd_ask(args: argparse.Namespace) -> int:
    import anthropic

    from fjordroast.agent.dashboard_spec import DashboardSpecError, generate_dashboard_specs
    from fjordroast.agent.narrative import generate_narrative_caption
    from fjordroast.agent.nl_to_query import AgentError, nl_to_logical_query

    model = load_semantic_model(SEMANTIC_MODEL_DIR)
    client = anthropic.Anthropic()
    con = get_connection()

    print(f"Asking: {args.question!r}")
    try:
        lq = nl_to_logical_query(client, model, args.question, identity=args.identity, anthropic_model=args.model)
    except AgentError as exc:
        print(f"Agent could not produce a valid logical query: {exc}", file=sys.stderr)
        return 1
    print(f"Logical query: {lq.model_dump_json(exclude_none=True)}")

    df, sql = execute_logical_query(con, model, lq, identity=args.identity)
    print(f"Rows: {len(df)}")

    specs = None
    try:
        specs = generate_dashboard_specs(client, args.question, df, anthropic_model=args.model)
        print(f"Generated {len(specs)} chart spec(s).")
    except DashboardSpecError as exc:
        print(f"Falling back to a plain table (spec generation failed): {exc}", file=sys.stderr)

    try:
        narrative = generate_narrative_caption(client, args.question, df, anthropic_model=args.model)
    except Exception as exc:  # noqa: BLE001 - narrative is best-effort, never fatal
        narrative = ""
        print(f"(narrative caption generation failed: {exc})", file=sys.stderr)

    record_id = uuid.uuid4().hex[:10]
    html_path = DASHBOARDS_DIR / f"{record_id}.html"
    write_dashboard(
        html_path,
        title=title_from_question(args.question),
        question=args.question,
        df=df,
        specs=specs,
        narrative=narrative or "(no narrative generated)",
        sql=sql,
    )

    store = DashboardStore(STORE_PATH)
    store.save(
        question=args.question,
        logical_query=lq.model_dump(exclude_none=True),
        sql=sql,
        vega_spec=specs,
        narrative=narrative,
        identity=args.identity,
        model_version=model.meta.version,
        anthropic_model=args.model,
        html_path=str(html_path),
        record_id=record_id,
    )
    store.close()

    print(f"Dashboard saved: {html_path}  (id: {record_id})")
    if not args.no_open:
        try:
            webbrowser.open(html_path.resolve().as_uri())
        except Exception:  # noqa: BLE001 - opening a browser is best-effort
            pass
    return 0


def cmd_refresh(args: argparse.Namespace) -> int:
    model = load_semantic_model(SEMANTIC_MODEL_DIR)
    store = DashboardStore(STORE_PATH)
    record = store.get(args.id)
    if record is None:
        print(f"No dashboard with id {args.id!r}", file=sys.stderr)
        return 1

    con = get_connection()
    lq = LogicalQuery.model_validate(record.logical_query)
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
    store.close()
    print(f"Refreshed dashboard {record.id} -> {html_path} ({len(df)} rows, logical query unchanged)")
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    import uvicorn

    from fjordroast.server import build_app

    app = build_app(PROJECT_ROOT)
    uvicorn.run(app, host=args.host, port=args.port)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fjordroast", description="Fjord Roast conversational analytics prototype")
    sub = parser.add_subparsers(dest="command", required=True)

    p_ask = sub.add_parser("ask", help="Ask a natural-language question and generate a dashboard")
    p_ask.add_argument("question")
    p_ask.add_argument("--identity", default=None, help="Named identity for row-level access (see access/row_filters.yml)")
    p_ask.add_argument("--model", default=DEFAULT_MODEL, help=f"Anthropic model (default: {DEFAULT_MODEL})")
    p_ask.add_argument("--no-open", action="store_true", help="Don't open the dashboard in a browser")
    p_ask.set_defaults(func=cmd_ask)

    p_validate = sub.add_parser("validate", help="Validate the semantic model files (CI entry point)")
    p_validate.set_defaults(func=cmd_validate)

    p_refresh = sub.add_parser("refresh", help="Re-run a saved dashboard's logical query against current data")
    p_refresh.add_argument("id")
    p_refresh.set_defaults(func=cmd_refresh)

    p_serve = sub.add_parser("serve", help="Run a FastAPI chat + gallery server (stretch)")
    p_serve.add_argument("--host", default="127.0.0.1")
    p_serve.add_argument("--port", type=int, default=8420)
    p_serve.set_defaults(func=cmd_serve)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
