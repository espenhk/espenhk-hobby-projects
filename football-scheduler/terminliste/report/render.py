"""Machine-readable exports of a solver result.

HTML rendering lives in the sibling `football-scheduler-frontend/` prep
folder (see that project's `render.py`) — it renders the same
`views.build_option()` output this module exports as JSON. This module only
ever writes JSON: `write_json` is the original solver-metadata export used
for diffing/snapshots, and `write_frontend_json` is the richer, documented
data contract described in `CONTRACT.md`.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from ..model.loader import World
from ..model.schema import Season
from ..rounds.cup_schedule import CupSchedule
from ..solvers.base import SolverResult
from .frontend_schema import FrontendPayload
from .views import build_option, club_colors_for


def write_json(result: SolverResult, output_path: Path) -> Path:
    """Machine-readable twin of the HTML, for diffing and test snapshots."""
    payload = {
        "solver": result.solver,
        "iterations": result.iterations,
        "elapsed_s": round(result.elapsed_s, 2),
        "notes": result.notes,
        "options": [
            {
                "label": candidate.label,
                "seed": candidate.seed,
                "hard_violations": candidate.score.hard_violations,
                "soft_total": round(candidate.score.soft_total, 2),
                "points": round(candidate.score.points, 1),
                "breakdown": [
                    {
                        "constraint": r.constraint_id,
                        "kind": r.kind,
                        "total": round(r.total, 2),
                        "count": r.count,
                    }
                    for r in candidate.score.results
                ],
                "matches": [
                    {
                        "date": m.date.isoformat(),
                        "competition": m.competition_id,
                        "round": m.round_index + 1,
                        "leg": m.leg,
                        "home": m.home_team,
                        "away": m.away_team,
                        "venue": m.venue,
                    }
                    for m in candidate.matches
                ],
            }
            for candidate in result.candidates
        ],
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return output_path


def build_frontend_payload(
    world: World,
    season: Season,
    result: SolverResult,
    cup_schedules: list[CupSchedule] | None = None,
) -> FrontendPayload:
    """The full data contract for a solver result, as a validated model.

    Reuses `views.build_option()` — the same enrichment (resolved names,
    weekday strings, dual-club colors, the `paired` flag, cup rounds) the
    HTML report renders — so the JSON contract and the HTML report can never
    disagree about what a schedule looks like.
    """
    club_colors = club_colors_for(world)
    cup_schedules = cup_schedules or []
    options = [
        build_option(world, season, candidate, club_colors, cup_schedules) for candidate in result.candidates
    ]
    return FrontendPayload(
        generated_at=datetime.now(timezone.utc),
        season_id=season.id,
        season_year=season.year,
        season_start=season.start,
        season_end=season.end,
        solver=result.solver,
        club_colors=club_colors,
        options=options,
    )


def write_frontend_json(
    world: World,
    season: Season,
    result: SolverResult,
    output_path: Path,
    cup_schedules: list[CupSchedule] | None = None,
) -> Path:
    """Write the documented frontend data contract (see CONTRACT.md)."""
    payload = build_frontend_payload(world, season, result, cup_schedules)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload.model_dump(mode="json"), indent=2), encoding="utf-8")
    return output_path
