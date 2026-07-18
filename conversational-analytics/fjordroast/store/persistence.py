"""The "living dashboard" store — a local SQLite table of
{question, logical_query, sql, vega_spec, model_version, created_at}.

`refresh <id>` re-runs the stored *logical query* (never the LLM) against
current data and regenerates the HTML, which is what makes a pinned
dashboard a deterministic, reproducible artifact rather than a one-off chat
response.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS dashboards (
    id TEXT PRIMARY KEY,
    question TEXT NOT NULL,
    logical_query TEXT NOT NULL,
    sql TEXT NOT NULL,
    vega_spec TEXT,
    narrative TEXT NOT NULL,
    identity TEXT,
    model_version TEXT NOT NULL,
    anthropic_model TEXT,
    html_path TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
)
"""


@dataclass
class DashboardRecord:
    id: str
    question: str
    logical_query: dict
    sql: str
    vega_spec: list[dict] | None
    narrative: str
    identity: str | None
    model_version: str
    anthropic_model: str | None
    html_path: str
    created_at: str
    updated_at: str

    @classmethod
    def _from_row(cls, row: sqlite3.Row) -> "DashboardRecord":
        return cls(
            id=row["id"],
            question=row["question"],
            logical_query=json.loads(row["logical_query"]),
            sql=row["sql"],
            vega_spec=json.loads(row["vega_spec"]) if row["vega_spec"] else None,
            narrative=row["narrative"],
            identity=row["identity"],
            model_version=row["model_version"],
            anthropic_model=row["anthropic_model"],
            html_path=row["html_path"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


class DashboardStore:
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._con = sqlite3.connect(self.db_path)
        self._con.row_factory = sqlite3.Row
        self._con.execute(SCHEMA)
        self._con.commit()

    def save(
        self,
        *,
        question: str,
        logical_query: dict,
        sql: str,
        vega_spec: list[dict] | None,
        narrative: str,
        identity: str | None,
        model_version: str,
        anthropic_model: str | None,
        html_path: str,
        record_id: str | None = None,
    ) -> DashboardRecord:
        now = datetime.now(timezone.utc).isoformat()
        rid = record_id or uuid.uuid4().hex[:12]
        self._con.execute(
            """
            INSERT INTO dashboards
                (id, question, logical_query, sql, vega_spec, narrative, identity,
                 model_version, anthropic_model, html_path, created_at, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(id) DO UPDATE SET
                sql = excluded.sql,
                vega_spec = COALESCE(excluded.vega_spec, dashboards.vega_spec),
                html_path = excluded.html_path,
                updated_at = excluded.updated_at
            """,
            (
                rid,
                question,
                json.dumps(logical_query),
                sql,
                json.dumps(vega_spec) if vega_spec else None,
                narrative,
                identity,
                model_version,
                anthropic_model,
                str(html_path),
                now,
                now,
            ),
        )
        self._con.commit()
        saved = self.get(rid)
        assert saved is not None, "row was just inserted/updated by id, so it must exist"
        return saved

    def get(self, record_id: str) -> DashboardRecord | None:
        row = self._con.execute("SELECT * FROM dashboards WHERE id = ?", (record_id,)).fetchone()
        return DashboardRecord._from_row(row) if row else None

    def list(self) -> list[DashboardRecord]:
        rows = self._con.execute("SELECT * FROM dashboards ORDER BY created_at DESC").fetchall()
        return [DashboardRecord._from_row(r) for r in rows]

    def close(self) -> None:
        self._con.close()
