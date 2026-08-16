"""The frontend data contract: what `write_frontend_json` actually promises.

These models are the JSON contract itself — `FrontendPayload.model_json_schema()`
is what gets committed to `schemas/season_frontend.schema.json`, and
`FrontendPayload(...).model_dump(mode="json")` is what gets written to disk.
Field shapes mirror what `views.build_option()` already produces; see
`CONTRACT.md` for what each field means and why.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel


class FrontendHeadline(BaseModel):
    value: str
    label: str


class FrontendResultRow(BaseModel):
    id: str
    kind: str
    total: float
    count: int
    description: str
    examples: list[str]
    more: int


class FrontendMatch(BaseModel):
    date: date
    weekday: str
    home: str
    away: str
    venue: str
    color: str
    away_color: str
    paired: bool
    leg: int


class FrontendRound(BaseModel):
    index: int
    leg: int
    dates: str
    matches: list[FrontendMatch]


class FrontendCompetitionView(BaseModel):
    id: str
    name: str
    is_cup: Literal[False] = False
    preferred_weekday: str
    match_count: int
    rounds: list[FrontendRound]


class FrontendCupRound(BaseModel):
    index: int
    name: str
    dates: str
    team_count: int
    note: str


class FrontendCupView(BaseModel):
    """A cup competition's rounds — no fixtures, just resolved date windows.

    Pairings within a cup round are drawn round by round and unknown ahead
    of time, unlike a league's `FrontendCompetitionView`, so there is no
    `matches` list here — see CONTRACT.md.
    """

    id: str
    name: str
    is_cup: Literal[True] = True
    match_count: int
    rounds: list[FrontendCupRound]


class FrontendOption(BaseModel):
    label: str
    seed: int | None
    feasible: bool
    hard_violations: int
    soft_total: float
    points: float
    headlines: list[FrontendHeadline]
    problems: list[FrontendResultRow]
    upsides: list[FrontendResultRow]
    breakdown: list[FrontendResultRow]
    competitions: list[FrontendCompetitionView | FrontendCupView]


class FrontendPayload(BaseModel):
    generated_at: datetime
    season_id: str
    season_year: int
    season_start: date
    season_end: date
    solver: str
    club_colors: dict[str, str]
    options: list[FrontendOption]
