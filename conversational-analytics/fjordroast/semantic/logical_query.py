"""The structured logical query — the only thing the NL agent is allowed to
produce. No SQL, no raw column aggregations: metrics are referenced by name
and expand centrally in query_builder.py.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

FilterOp = Literal["=", "!=", ">", ">=", "<", "<=", "in", "not in", "between"]
TimeGrain = Literal["day", "week", "month", "quarter", "year"]
SortDirection = Literal["asc", "desc"]


class Filter(BaseModel):
    field: str = Field(description="Fully qualified 'table.column', e.g. 'dim_store.city'.")
    op: FilterOp
    value: object = Field(description="Scalar for =/!=/comparisons, a list for in/not in/between.")


class SortSpec(BaseModel):
    field: str = Field(description="A requested metric name or a requested group_by field.")
    direction: SortDirection = "desc"


class LogicalQuery(BaseModel):
    metrics: list[str] = Field(min_length=1, description="Metric names from metrics/*.yml.")
    group_by: list[str] = Field(default_factory=list, description="Fully qualified 'table.column' dimensions.")
    filters: list[Filter] = Field(default_factory=list)
    time_grain: TimeGrain | None = Field(
        default=None, description="Only meaningful when 'dim_date.date' is in group_by."
    )
    sort: list[SortSpec] = Field(default_factory=list)
    limit: int | None = Field(default=None, gt=0, le=5000)

    @classmethod
    def json_schema_for_tool(cls) -> dict:
        """A JSON schema suitable for an Anthropic tool-use `input_schema`,
        stripped of the `$defs`/`title` noise the model doesn't need."""
        schema = cls.model_json_schema()
        schema.pop("title", None)
        return schema
