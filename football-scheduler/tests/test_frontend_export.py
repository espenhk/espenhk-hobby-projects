"""The frontend JSON contract: round-trips cleanly, and the committed
example fixture hasn't drifted out of sync with the current schema.

See CONTRACT.md for what the payload means; this only checks the shape.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import factories as f
import pytest

from terminliste.model.travel import HaversineTravelModel
from terminliste.report.frontend_schema import FrontendPayload
from terminliste.report.render import build_frontend_payload
from terminliste.scoring.base import EvalContext
from terminliste.scoring.registry import build_constraints
from terminliste.solvers import SolveRequest, get_scheduler

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _small_dual_club_world():
    """Two teams sharing one club, so a `paired` back-to-back home day is reachable."""
    venue_a = f.venue("venue_a")
    venue_b = f.venue("venue_b")
    men_team = f.team("dual_m", "dual_club", "venue_a", gender="men")
    women_team = f.team("dual_w", "dual_club", "venue_a", gender="women")
    other_men = [f.team(f"m{i}", f"club{i}", "venue_b", gender="men") for i in range(3)]
    other_women = [f.team(f"w{i}", f"club{i}", "venue_b", gender="women") for i in range(3)]

    clubs = [f.club("dual_club", [men_team, women_team])]
    for i in range(3):
        clubs.append(f.club(f"club{i}", [other_men[i], other_women[i]]))

    comp_m = f.competition("men", [men_team.id] + [t.id for t in other_men], gender="men")
    comp_w = f.competition("women", [women_team.id] + [t.id for t in other_women], gender="women")
    world = f.world(clubs, [venue_a, venue_b], [comp_m, comp_w])
    season = f.season(competitions=["men", "women"], start=date(2026, 3, 1), end=date(2026, 6, 30))
    return world, season, [comp_m, comp_w]


@pytest.fixture(scope="module")
def solved():
    world, season, competitions = _small_dual_club_world()
    constraints = build_constraints(world, season, competitions)
    travel = HaversineTravelModel(world)
    ctx = EvalContext(world=world, season=season, travel=travel)
    scheduler = get_scheduler("local")
    request = SolveRequest(
        world=world,
        season=season,
        competitions=competitions,
        constraints=constraints,
        ctx=ctx,
        seed=1,
        top_n=1,
        time_budget_s=3.0,
    )
    result = scheduler.solve(request)
    return world, season, result


def test_frontend_payload_round_trips(solved):
    world, season, result = solved
    payload = build_frontend_payload(world, season, result)

    dumped = payload.model_dump(mode="json")
    reloaded = FrontendPayload.model_validate(json.loads(json.dumps(dumped)))

    assert reloaded.season_id == season.id
    assert reloaded.solver == result.solver
    assert len(reloaded.options) == len(result.candidates)


def test_frontend_payload_marks_dual_club_pairing(solved):
    world, season, result = solved
    payload = build_frontend_payload(world, season, result)

    assert "dual_club" in payload.club_colors
    matches = [
        m
        for option in payload.options
        for comp in option.competitions
        for rnd in comp.rounds
        for m in rnd.matches
    ]
    assert any(m.color for m in matches), "no match carries the dual club's color"


def test_committed_example_fixture_matches_current_schema():
    fixture_path = PROJECT_ROOT / "schemas" / "example_2026.frontend.json"
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    FrontendPayload.model_validate(payload)
