"""Pydantic models mirroring the YAML files under /data/.

Pure data containers — no scheduling logic, no I/O. `loader.py` reads the YAML
into these and cross-checks referential integrity; everything downstream works
off the validated result and never touches the raw YAML.

The shape here is deliberately wider than the first version needs. `Team.level`
exists so reserve sides are a data edit rather than a refactor, and
`Competition.format` is a discriminator so cups can be added alongside leagues
without disturbing the league path.
"""

from __future__ import annotations

from datetime import date
from typing import Iterable, Literal

from pydantic import BaseModel, Field, field_validator

Gender = Literal["men", "women"]
TeamLevel = Literal["senior", "second", "youth"]
Surface = Literal["grass", "artificial", "hybrid"]
CompetitionFormat = Literal["league", "cup"]

WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
Weekday = Literal["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]

# Rough bounding box for mainland Norway, used by the data validator to catch
# swapped or mistyped coordinates.
NORWAY_LAT_RANGE = (57.0, 72.0)
NORWAY_LON_RANGE = (4.0, 32.0)


class Venue(BaseModel):
    id: str
    name: str
    city: str
    lat: float
    lon: float
    capacity: int
    surface: Surface = "grass"


class Team(BaseModel):
    id: str
    gender: Gender
    level: TeamLevel = "senior"
    home_venue: str

    # Filled in by the loader once the owning club is known, so a Team can be
    # passed around on its own without dragging the club along.
    club_id: str = ""


class Club(BaseModel):
    id: str
    name: str
    short_name: str
    city: str
    teams: list[Team]


class CupRound(BaseModel):
    """One round of a knockout cup: a name and the date its ties are played on.

    A single date is enough — NFF schedules every tie of a round inside the
    same short window in practice, so there is no separate "date range" to
    track. Pairings are drawn round by round and are not known ahead of time,
    so this records only when the round falls, not who plays whom.
    """

    id: str
    name: str
    date: date
    note: str = ""


class Competition(BaseModel):
    """A league or a cup. `format` discriminates the two.

    A league's fixtures are generated and dated by the solver. A cup's rounds
    are real-world fixed dates (`cup_rounds`) that the solver treats as given
    rather than something to search over — see `cup_rounds` and
    `CupRoundConflict` in `scoring/hard.py`.
    """

    id: str
    name: str
    season: int
    gender: Gender
    format: CompetitionFormat = "league"

    rounds_per_pairing: int = 2
    team_count: int
    teams: list[str]

    preferred_weekday: Weekday = "sunday"
    min_rest_days: int = 3
    match_window_days: int = 3
    comfortable_rest_days: int = 6
    weights: dict[str, float] = Field(default_factory=dict)

    # Cup-only: the real-world rounds this competition's teams are entered
    # into, in the order they are played. Empty for a league.
    cup_rounds: list[CupRound] = Field(default_factory=list)

    @field_validator("rounds_per_pairing")
    @classmethod
    def _at_least_one_round(cls, v: int) -> int:
        if v < 1:
            raise ValueError("rounds_per_pairing must be at least 1")
        return v

    @property
    def rounds(self) -> int:
        """Total rounds.

        League: (n-1) per leg for even n, n for odd n (bye rounds). Cup: the
        number of real-world rounds its teams are entered into.
        """
        if self.format == "cup":
            return len(self.cup_rounds)
        n = self.team_count
        per_leg = n - 1 if n % 2 == 0 else n
        return per_leg * self.rounds_per_pairing

    @property
    def matches_per_leg(self) -> int:
        return self.team_count * (self.team_count - 1) // 2

    @property
    def total_matches(self) -> int:
        """League only — a cup's pairings are drawn round by round and are
        not modelled as fixtures, so this is 0 for `format == "cup"`."""
        if self.format == "cup":
            return 0
        return self.matches_per_leg * self.rounds_per_pairing


class DatedNote(BaseModel):
    """A date carrying a human-readable reason, for blackouts and the like."""

    date: date
    reason: str = ""


class VenueBlackout(BaseModel):
    venue: str
    date: date
    reason: str = ""


class FixedRequirement(BaseModel):
    """A date that must carry a match, with a named team at home.

    `hard=True` makes it a constraint the solver must satisfy; `hard=False`
    demotes it to a scored preference.
    """

    id: str
    date: date
    home_team: str
    competition: str
    hard: bool = True
    reason: str = ""
    weight: float = 50.0


class Season(BaseModel):
    # Coerced to str so `id: 2026` in YAML — the natural way to write it —
    # loads without ceremony.
    id: str
    year: int

    @field_validator("id", mode="before")
    @classmethod
    def _id_to_str(cls, v: object) -> str:
        return str(v)
    start: date
    end: date
    competitions: list[str]
    # Cup competitions tied to this season, kept separate from `competitions`
    # because they are not fed to the round-robin/solver pipeline: their
    # rounds are fixed real-world dates, not something to be scheduled. A cup
    # round can fall outside `start`..`end` (the 2027 Norwegian Cup starts in
    # August 2026 and runs into the following spring) — that is expected, not
    # a data error.
    cup_competitions: list[str] = Field(default_factory=list)
    global_blackouts: list[DatedNote] = Field(default_factory=list)
    discouraged_dates: list[DatedNote] = Field(default_factory=list)
    venue_blackouts: list[VenueBlackout] = Field(default_factory=list)
    fixed_requirements: list[FixedRequirement] = Field(default_factory=list)


class TravelOverride(BaseModel):
    a: str
    b: str
    # None means "no reasonable surface connection" — treated as infinite.
    hours: float | None = None
    note: str = ""


# -- scheduling artefacts ---------------------------------------------------


class Fixture(BaseModel):
    """An unscheduled pairing: who plays whom, in which leg and round."""

    competition_id: str
    home_team: str
    away_team: str
    leg: int
    round_index: int

    @property
    def key(self) -> str:
        return f"{self.competition_id}:{self.round_index}:{self.home_team}-{self.away_team}"


def cup_rest_windows(competitions: Iterable[Competition]) -> dict[str, list[tuple[date, int]]]:
    """Per-team (cup round date, min rest days) pairs, for conflict-avoidance.

    Which teams reach which round is not known in advance, so every team
    entered in a cup is treated as still alive through the final — this
    blocks a window around every remaining round rather than just the ones a
    team is realistically still in. Shared by the greedy placer and
    `CupRoundConflict`, so both agree on what "too close to a cup match"
    means.
    """
    windows: dict[str, list[tuple[date, int]]] = {}
    for competition in competitions:
        if competition.format != "cup":
            continue
        for round_ in competition.cup_rounds:
            for team_id in competition.teams:
                windows.setdefault(team_id, []).append((round_.date, competition.min_rest_days))
    return windows


class Match(BaseModel):
    """A fixture placed on the calendar."""

    competition_id: str
    home_team: str
    away_team: str
    leg: int
    round_index: int
    date: date
    venue: str

    @property
    def key(self) -> str:
        return f"{self.competition_id}:{self.round_index}:{self.home_team}-{self.away_team}"
