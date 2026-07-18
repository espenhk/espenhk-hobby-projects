"""Builds the compact schema-plus-glossary text block used to ground the
NL-to-logical-query agent. This — plus the model's `ai_instructions` — is the
entire vocabulary the LLM is allowed to draw from.
"""

from __future__ import annotations

from .loader import SemanticModel


def build_grounding_block(model: SemanticModel) -> str:
    lines: list[str] = []

    lines.append(f"# {model.meta.name} (v{model.meta.version})")
    lines.append(model.meta.description.strip())
    lines.append("")

    ai = model.meta.ai_instructions
    if ai.business_context:
        lines.append("## Business context")
        lines.extend(f"- {item}" for item in ai.business_context)
        lines.append("")
    if ai.terminology:
        lines.append("## Terminology")
        lines.extend(f"- {item}" for item in ai.terminology)
        lines.append("")
    if ai.do_dont:
        lines.append("## Rules")
        lines.extend(f"- {item}" for item in ai.do_dont)
        lines.append("")

    lines.append("## Tables and dimensions")
    lines.append("Reference dimensions/filters as 'table.column'.")
    for table in model.tables.values():
        lines.append(f"\n### {table.name}  ({table.grain})")
        lines.append(table.description.strip())
        for col in table.visible_columns():
            syn = f" (also called: {', '.join(col.synonyms)})" if col.synonyms else ""
            key = " [key]" if col.is_key else ""
            lines.append(f"- {table.name}.{col.name}: {col.type}{key} — {col.description}{syn}")

    lines.append("\n## Metrics")
    lines.append("Reference these by name in `metrics`. Never invent a metric.")
    for metric in model.metrics.values():
        syn = f" (also called: {', '.join(metric.synonyms)})" if metric.synonyms else ""
        dims = ", ".join(metric.sliceable_dimensions) or "none"
        lines.append(f"\n- {metric.name} [{metric.format}]: {metric.description}{syn}")
        lines.append(f"  sliceable by: {dims}")

    lines.append("\n## Relationships")
    for rel in model.relationships:
        lines.append(f"- {rel.from_table}.{rel.from_column} -> {rel.to_table}.{rel.to_column} ({rel.cardinality})")

    return "\n".join(lines)
