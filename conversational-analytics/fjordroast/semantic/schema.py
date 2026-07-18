"""Pydantic models mirroring the YAML files under /semantic_model/.

These are pure data containers — no SQL, no I/O. `loader.py` reads the YAML
into these models and cross-checks referential integrity; `query_builder.py`
consumes the validated result.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

ColumnType = Literal["string", "integer", "float", "date", "boolean"]
MetricFormat = Literal["NOK", "number", "percent"]
MetricKind = Literal["simple", "basket_ratio"]
Cardinality = Literal["many_to_one", "one_to_one", "one_to_many"]


class AIInstructions(BaseModel):
    business_context: list[str] = Field(default_factory=list)
    terminology: list[str] = Field(default_factory=list)
    do_dont: list[str] = Field(default_factory=list)


class ModelMeta(BaseModel):
    name: str
    version: str
    description: str
    ai_instructions: AIInstructions


class ColumnDef(BaseModel):
    name: str
    type: ColumnType
    description: str
    is_key: bool = False
    hidden_from_ai: bool = False
    synonyms: list[str] = Field(default_factory=list)


class TableDef(BaseModel):
    name: str
    source: str
    grain: str
    description: str
    columns: list[ColumnDef]

    def column(self, name: str) -> ColumnDef | None:
        return next((c for c in self.columns if c.name == name), None)

    def visible_columns(self) -> list[ColumnDef]:
        return [c for c in self.columns if not c.hidden_from_ai]


class Relationship(BaseModel):
    name: str
    from_table: str
    from_column: str
    to_table: str
    to_column: str
    cardinality: Cardinality
    nullable: bool = False


class MetricDef(BaseModel):
    name: str
    description: str
    kind: MetricKind = "simple"
    # kind == "simple"
    expression: str | None = None
    # kind == "basket_ratio"
    numerator_condition: str | None = None
    denominator_condition: str | None = None

    format: MetricFormat = "number"
    synonyms: list[str] = Field(default_factory=list)
    sliceable_dimensions: list[str] = Field(default_factory=list)


class RowFilterEntry(BaseModel):
    identity: str
    description: str = ""
    predicate: str


class RowFilters(BaseModel):
    filters: list[RowFilterEntry] = Field(default_factory=list)

    def predicate_for(self, identity: str | None) -> str | None:
        if identity is None:
            return None
        for f in self.filters:
            if f.identity == identity:
                return f.predicate
        raise KeyError(f"Unknown identity {identity!r}; not declared in access/row_filters.yml")


class VerifiedAnswer(BaseModel):
    question: str
    logical_query: dict
