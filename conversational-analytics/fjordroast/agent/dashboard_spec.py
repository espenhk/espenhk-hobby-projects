"""Step 2 of the dashboard flow: (question, columns, sample rows) -> Vega-Lite spec(s).

The model is asked to emit raw JSON only (a single spec, or a small array for a
mini-dashboard). We validate every spec against the pinned Vega-Lite v6 JSON
schema plus a whitelist check that every referenced `field` exists in the
result's columns. One repair round-trip on failure; the caller falls back to
a plain HTML table if that also fails.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import jsonschema
import pandas as pd

DEFAULT_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-opus-4-8")

_SCHEMA_PATH = Path(__file__).resolve().parent.parent / "dashboard" / "schemas" / "vega-lite-v6.schema.json"
_VEGA_LITE_SCHEMA = json.loads(_SCHEMA_PATH.read_text())
_VALIDATOR = jsonschema.Draft7Validator(_VEGA_LITE_SCHEMA)

SYSTEM_PROMPT = """You are a data-visualization assistant for a small business analytics tool.

Given a business question and the columns/sample rows of the query result that answers it,
respond with ONLY raw JSON — a single Vega-Lite v6 spec object, or a JSON array of 1-4 spec
objects for a small multi-chart dashboard. No prose, no markdown code fences, no commentary.

Rules:
- Every spec must have a top-level "data" key whose value is exactly {"name": "table"} —
  i.e. each spec looks like {"data": {"name": "table"}, "mark": ..., "encoding": ...}.
  Never inline data and never omit this key.
- Reference ONLY the column names you were given. Never invent a field name.
- Add a "tooltip" encoding covering the marks' key fields, on every spec.
- If a spec encodes a temporal/date field on the x-axis, add an interval-selection "params"
  entry on that spec (a brush) so the user can zoom into a date range.
- Pick chart types appropriate to the question: a time trend is usually a line or area mark;
  a comparison across categories is usually a bar; a relationship between two metrics is
  usually a point (scatter), optionally colored/sized by a third field.
- Keep it legible: a clear "title", a short "description", and no more chart complexity than
  the question calls for.
"""


class DashboardSpecError(Exception):
    """Raised when no valid Vega-Lite spec could be produced, even after repair."""


def _extract_json(text: str):
    text = text.strip()
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.DOTALL)
    if fence:
        text = fence.group(1)
    return json.loads(text)


def _field_refs(node) -> set[str]:
    fields: set[str] = set()
    if isinstance(node, dict):
        field = node.get("field")
        if isinstance(field, str):
            fields.add(field)
        for value in node.values():
            fields |= _field_refs(value)
    elif isinstance(node, list):
        for item in node:
            fields |= _field_refs(item)
    return fields


def _derived_field_names(node) -> set[str]:
    """Field names a `transform` entry (aggregate/calculate/window/...)
    produces via its 'as' key — these are legitimate encoding targets even
    though they don't exist in the raw result columns."""
    names: set[str] = set()
    if isinstance(node, dict):
        as_value = node.get("as")
        if isinstance(as_value, str):
            names.add(as_value)
        elif isinstance(as_value, list):
            names.update(v for v in as_value if isinstance(v, str))
        for value in node.values():
            names |= _derived_field_names(value)
    elif isinstance(node, list):
        for item in node:
            names |= _derived_field_names(item)
    return names


def validate_specs(specs: list[dict], columns: list[str]) -> list[str]:
    errors: list[str] = []
    for i, spec in enumerate(specs):
        for err in _VALIDATOR.iter_errors(spec):
            path = "/".join(str(p) for p in err.path)
            errors.append(f"spec[{i}]{('.' + path) if path else ''}: {err.message}")
        if spec.get("data") != {"name": "table"}:
            errors.append(f"spec[{i}]: 'data' must be exactly {{'name': 'table'}}")
        allowed = set(columns) | _derived_field_names(spec)
        unknown = _field_refs(spec) - allowed
        if unknown:
            errors.append(f"spec[{i}]: references unknown field(s) {sorted(unknown)}")
    return errors


def generate_dashboard_specs(
    client, question: str, df: pd.DataFrame, anthropic_model: str = DEFAULT_MODEL
) -> list[dict]:
    columns = list(df.columns)
    sample_rows = json.loads(df.head(5).to_json(orient="records", date_format="iso"))
    user_prompt = (
        f"Question: {question}\n"
        f"Result columns: {columns}\n"
        f"Sample rows: {json.dumps(sample_rows)}\n"
        f"Total rows in result: {len(df)}"
    )

    def ask(extra: str | None = None) -> tuple[list[dict] | None, list[str]]:
        content = user_prompt if not extra else f"{user_prompt}\n\n{extra}"
        response = client.messages.create(
            model=anthropic_model,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": content}],
        )
        text = "".join(b.text for b in response.content if b.type == "text")
        try:
            parsed = _extract_json(text)
        except (json.JSONDecodeError, ValueError) as exc:
            return None, [f"Response was not valid JSON: {exc}"]
        specs = parsed if isinstance(parsed, list) else [parsed]
        return specs, validate_specs(specs, columns)

    specs, errors = ask()
    if specs is not None and not errors:
        return specs

    repair_note = "Your previous response failed validation:\n- " + "\n- ".join(errors) + "\nReturn corrected JSON only, no prose."
    specs2, errors2 = ask(repair_note)
    if specs2 is not None and not errors2:
        return specs2

    raise DashboardSpecError(
        "Vega-Lite spec generation failed after one repair attempt:\n- " + "\n- ".join(errors2 or errors)
    )
