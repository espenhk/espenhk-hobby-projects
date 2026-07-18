"""A short LLM-written caption summarizing the result — narrative only, never
a source of numbers (the numbers themselves come from the DataFrame already
computed by DuckDB, and are handed to the model only as context)."""

from __future__ import annotations

import json
import os

import pandas as pd

DEFAULT_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-opus-4-8")

SYSTEM_PROMPT = """You write a one-to-two sentence caption for a business dashboard.
Given the question and the resulting data (columns, a few sample rows, row count),
summarize the headline takeaway in plain business language. No markdown, no bullet
points, just the caption text. Do not invent numbers beyond what is shown to you."""


def generate_narrative_caption(client, question: str, df: pd.DataFrame, anthropic_model: str = DEFAULT_MODEL) -> str:
    sample_rows = json.loads(df.head(8).to_json(orient="records", date_format="iso"))
    user_prompt = (
        f"Question: {question}\n"
        f"Columns: {list(df.columns)}\n"
        f"Rows (sample, {len(df)} total): {json.dumps(sample_rows)}"
    )
    response = client.messages.create(
        model=anthropic_model,
        max_tokens=256,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )
    return "".join(b.text for b in response.content if b.type == "text").strip()
