"""Derives the display-ready view model from a solver result.

Shared by both consumers of a solved schedule: the HTML report renderer
(in the sibling `football-scheduler-frontend/` prep folder) and the JSON
frontend export (`write_frontend_json` in `render.py`). Neither consumer
resolves ids to names, computes weekday strings, or figures out the
dual-club `paired` (back-to-back home day) flag on its own — that
enrichment lives here exactly once.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta

from ..model.loader import World
from ..model.schema import Match, Season
from ..rounds.cup_schedule import CupSchedule
from ..scoring.base import ConstraintResult, Score
from ..scoring.registry import describe
from ..solvers.base import Candidate

# Distinct hues for the clubs that field two teams — the ones whose coupling
# the whole exercise is about. Everyone else stays neutral so the dual clubs
# stand out in the calendar grid.
DUAL_CLUB_COLORS = [
    "#c0392b",
    "#2471a3",
    "#1e8449",
    "#b9770e",
    "#7d3c98",
    "#117a8b",
]


def club_colors_for(world: World) -> dict[str, str]:
    """One stable hex color per dual club, keyed by club id."""
    return {
        club.id: DUAL_CLUB_COLORS[i % len(DUAL_CLUB_COLORS)]
        for i, club in enumerate(sorted(world.dual_clubs(), key=lambda c: c.id))
    }


def build_option(
    world: World,
    season: Season,
    candidate: Candidate,
    club_colors: dict[str, str],
    cup_schedules: list[CupSchedule] | None = None,
    full_diagnostics: bool = False,
) -> dict:
    score = candidate.score
    limit = 200 if full_diagnostics else 4
    return {
        "label": candidate.label,
        "seed": candidate.seed,
        "full": full_diagnostics,
        "feasible": score.feasible,
        "hard_violations": score.hard_violations,
        "soft_total": score.soft_total,
        "points": score.points,
        "headlines": headlines(world, candidate),
        "hard_violation_detail": (
            [_result_row(r, full=True) for r in score.hard_results() if r.count]
            if full_diagnostics
            else []
        ),
        "problems": [_result_row(r, full=full_diagnostics) for r in score.biggest_problems(limit=limit)],
        "upsides": [_result_row(r, full=full_diagnostics) for r in score.biggest_upsides(limit=limit)],
        "breakdown": [_result_row(r, full=True) for r in _ordered_results(score)],
        "competitions": competition_views(world, candidate, club_colors) + cup_views(cup_schedules or []),
    }


def _ordered_results(score: Score) -> list[ConstraintResult]:
    """Hard rules first, then soft ordered by how much they moved the score."""
    hard = sorted(score.hard_results(), key=lambda r: (r.count == 0, r.constraint_id))
    soft = sorted(score.soft_results(), key=lambda r: -abs(r.total))
    return hard + soft


def _result_row(result: ConstraintResult, full: bool = False) -> dict:
    return {
        "id": result.constraint_id,
        "kind": result.kind,
        "total": result.total,
        "count": result.count,
        "description": describe(result.constraint_id),
        # A handful of concrete examples: enough to judge whether the number
        # means anything, not so many that the page becomes a log file.
        "examples": [e.detail for e in result.events[: (8 if full else 3)] if e.detail],
        "more": max(0, len([e for e in result.events if e.detail]) - (8 if full else 3)),
    }


def headlines(world: World, candidate: Candidate) -> list[dict]:
    """The three numbers a reader checks first."""
    score = candidate.score
    matches = candidate.matches
    result: list[dict] = []

    weekday = score.result("preferred_weekday")
    if weekday is not None and matches:
        result.append(
            {
                "value": f"{100.0 * weekday.count / len(matches):.0f}%",
                "label": "on the preferred weekday",
            }
        )

    home_pairs = score.result("consecutive_home_days")
    if home_pairs is not None:
        result.append(
            {"value": str(home_pairs.count), "label": "back-to-back home days"}
        )

    away_pairs = score.result("consecutive_away_days")
    if away_pairs is not None:
        result.append(
            {"value": str(away_pairs.count), "label": "paired away days within travel range"}
        )

    return result


def competition_views(world: World, candidate: Candidate, club_colors: dict[str, str]) -> list[dict]:
    by_competition: dict[str, list[Match]] = defaultdict(list)
    for match in candidate.matches:
        by_competition[match.competition_id].append(match)

    # Dates on which a dual club has a home match, so the calendar can flag the
    # back-to-back pairs that justify scheduling the leagues together.
    home_by_club: dict[str, set[date]] = defaultdict(set)
    for match in candidate.matches:
        club_id = world.team(match.home_team).club_id
        if club_id in club_colors:
            home_by_club[club_id].add(match.date)

    views: list[dict] = []
    for competition_id, matches in sorted(by_competition.items()):
        competition = world.competition(competition_id)
        rounds: dict[int, list[dict]] = defaultdict(list)
        for match in sorted(matches, key=lambda m: (m.date, m.home_team)):
            club_id = world.team(match.home_team).club_id
            paired = club_id in club_colors and _has_adjacent_home(
                home_by_club[club_id], match.date
            )
            rounds[match.round_index].append(
                {
                    "date": match.date,
                    "weekday": match.date.strftime("%a"),
                    "home": world.team_label(match.home_team),
                    "away": world.team_label(match.away_team),
                    "venue": world.venue(match.venue).name,
                    "color": club_colors.get(club_id, ""),
                    "away_color": club_colors.get(world.team(match.away_team).club_id, ""),
                    "paired": paired,
                    "leg": match.leg,
                }
            )

        views.append(
            {
                "id": competition_id,
                "name": competition.name,
                "is_cup": False,
                "preferred_weekday": competition.preferred_weekday,
                "match_count": len(matches),
                "rounds": [
                    {
                        "index": round_index + 1,
                        "leg": entries[0]["leg"],
                        "dates": _round_date_label(entries),
                        "matches": entries,
                    }
                    for round_index, entries in sorted(rounds.items())
                ],
            }
        )
    return views


def cup_views(cup_schedules: list[CupSchedule]) -> list[dict]:
    """Cup rounds, in the same shape `competition_views` uses for leagues.

    Pairings are drawn round by round and unknown ahead of time, so there is
    no fixture list here — just each round's resolved date span (a single day
    when every team landed on the same one) and how many of the tracked teams
    are still assumed to be in it.
    """
    views: list[dict] = []
    for schedule in sorted(cup_schedules, key=lambda s: s.competition_id):
        team_count = len(schedule.rounds[0].dates) if schedule.rounds else 0
        views.append(
            {
                "id": schedule.competition_id,
                "name": schedule.competition_name,
                "is_cup": True,
                "match_count": team_count,
                "rounds": [
                    {
                        "index": i + 1,
                        "name": placement.round_name,
                        "dates": (
                            placement.earliest_date.strftime("%d %b %Y")
                            if placement.spread_days == 0
                            else (
                                f"{placement.earliest_date.strftime('%d %b')} – "
                                f"{placement.latest_date.strftime('%d %b %Y')}"
                            )
                        ),
                        "team_count": len(placement.dates),
                        "note": placement.note,
                    }
                    for i, placement in enumerate(schedule.rounds)
                ],
            }
        )
    return views


def _has_adjacent_home(days: set[date], day: date) -> bool:
    return (day - timedelta(days=1)) in days or (day + timedelta(days=1)) in days


def _round_date_label(entries: list[dict]) -> str:
    days = sorted({e["date"] for e in entries})
    if not days:
        return ""
    if len(days) == 1:
        return days[0].strftime("%d %b")
    return f"{days[0].strftime('%d %b')} – {days[-1].strftime('%d %b')}"
