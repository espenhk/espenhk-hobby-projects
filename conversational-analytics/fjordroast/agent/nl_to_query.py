"""Step 1 of the query flow: natural language question -> structured LogicalQuery.

The agent never writes SQL and never invents metrics or dimensions — it is
grounded entirely in the semantic model's schema-plus-glossary block and
constrained to return the LogicalQuery shape. On validation failure we give
the model exactly one repair round-trip before giving up.
"""

from __future__ import annotations

import os

from ..semantic.grounding import build_grounding_block
from ..semantic.loader import SemanticModel
from ..semantic.logical_query import LogicalQuery
from ..semantic.query_builder import validate_logical_query

DEFAULT_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-opus-4-8")


class AgentError(Exception):
    """Raised when the agent cannot produce a valid logical query, even after repair."""


def _system_prompt(model: SemanticModel) -> str:
    grounding = build_grounding_block(model)
    return (
        "You are the query-planning agent for a conversational analytics tool over "
        "Fjord Roast's sales data. Your ONLY job is to translate the user's question "
        "into a structured logical query: chosen metrics, group-by dimensions, filters, "
        "time grain, sort, and limit.\n\n"
        "You must draw every metric and dimension name from the vocabulary below, using "
        "each dimension's exact 'table.column' form. Never write SQL. Never invent a metric "
        "or a column. Never fabricate numbers — you only choose structure, not values.\n\n"
        + grounding
    )


def nl_to_logical_query(
    client,
    model: SemanticModel,
    question: str,
    identity: str | None = None,
    anthropic_model: str = DEFAULT_MODEL,
) -> LogicalQuery:
    system_prompt = _system_prompt(model)
    user_prompt = f"Question: {question}"
    if identity:
        user_prompt += (
            f"\n\n(Note: this question is being asked by identity '{identity}'. "
            "Row-level access is enforced separately by the query engine — this does not "
            "change which fields you may reference.)"
        )

    def ask(extra: str | None = None) -> LogicalQuery:
        content = user_prompt if not extra else f"{user_prompt}\n\n{extra}"
        response = client.messages.parse(
            model=anthropic_model,
            max_tokens=2048,
            system=system_prompt,
            messages=[{"role": "user", "content": content}],
            output_format=LogicalQuery,
        )
        if response.parsed_output is None:
            raise AgentError("Agent response could not be parsed into a logical query.")
        return response.parsed_output

    logical_query = ask()
    errors = validate_logical_query(model, logical_query)
    if not errors:
        return logical_query

    repair_note = (
        "Your previous answer failed validation against the semantic model:\n- "
        + "\n- ".join(errors)
        + "\n\nReturn a corrected logical query using only the metrics and 'table.column' "
        "dimensions listed above."
    )
    repaired = ask(repair_note)
    repaired_errors = validate_logical_query(model, repaired)
    if repaired_errors:
        raise AgentError(
            "Logical query failed validation after one repair attempt:\n- "
            + "\n- ".join(repaired_errors)
        )
    return repaired
