"""Resolving a team's UEFA qualifying cascade to blocked date windows."""

from __future__ import annotations

from datetime import date

import pytest

import factories as f
from terminliste.rounds.european_schedule import (
    EuropeanCascadeError,
    resolve_european_commitments,
    resolve_team_cascade,
)


# -- resolve_team_cascade: a single competition, no cascade ------------------


def test_single_round_entry_gives_one_window():
    comp = f.competition(
        "cl",
        ["glimt"],
        format="european",
        european_rounds=[
            f.european_round(
                "playoff",
                entrants=["glimt"],
                window_start=date(2026, 8, 18),
                window_end=date(2026, 8, 26),
            )
        ],
    )
    windows = resolve_team_cascade("glimt", comp, {"cl": comp})
    assert len(windows) == 1
    assert windows[0].window_start == date(2026, 8, 18)
    assert windows[0].window_end == date(2026, 8, 26)
    assert windows[0].depth == 0


def test_win_progression_follows_the_next_round_when_the_team_is_listed():
    comp = f.competition(
        "cl",
        ["glimt"],
        format="european",
        european_rounds=[
            f.european_round("q3", entrants=["glimt"], forced_date=date(2026, 8, 4)),
            f.european_round("playoff", entrants=["glimt"], forced_date=date(2026, 8, 18)),
        ],
    )
    windows = resolve_team_cascade("glimt", comp, {"cl": comp})
    assert [w.window_start for w in windows] == [date(2026, 8, 4), date(2026, 8, 18)]
    assert [w.depth for w in windows] == [0, 1]


def test_win_progression_stops_when_the_team_is_not_listed_in_the_next_round():
    """Viking-shaped case: a team entering a later round directly must not
    be treated as having "progressed" from an earlier one it never played."""
    comp = f.competition(
        "cl",
        ["glimt", "viking"],
        format="european",
        european_rounds=[
            f.european_round("q3", entrants=["glimt"], forced_date=date(2026, 8, 4)),
            f.european_round(
                "playoff", entrants=["glimt", "viking"], forced_date=date(2026, 8, 18)
            ),
        ],
    )
    viking_windows = resolve_team_cascade("viking", comp, {"cl": comp})
    assert len(viking_windows) == 1
    assert viking_windows[0].window_start == date(2026, 8, 18)


def test_chain_ends_when_no_further_round_or_drop_to_applies():
    comp = f.competition(
        "cl",
        ["glimt"],
        format="european",
        european_rounds=[f.european_round("playoff", entrants=["glimt"], forced_date=date(2026, 8, 18))],
    )
    windows = resolve_team_cascade("glimt", comp, {"cl": comp})
    assert len(windows) == 1


def test_entrant_missing_from_every_round_raises():
    comp = f.competition(
        "cl",
        ["glimt"],
        format="european",
        european_rounds=[f.european_round("q3", entrants=["someone_else"], forced_date=date(2026, 8, 4))],
    )
    with pytest.raises(EuropeanCascadeError, match="not an entrant"):
        resolve_team_cascade("glimt", comp, {"cl": comp})


# -- resolve_team_cascade: cascading into another competition ----------------


def test_drop_to_cascades_into_the_named_round_of_another_competition():
    el = f.competition(
        "el",
        ["tromso"],
        format="european",
        european_rounds=[
            f.european_round(
                "q3",
                entrants=["tromso"],
                window_start=date(2026, 8, 6),
                window_end=date(2026, 8, 13),
                drop_to_competition="uecl",
                drop_to_round="playoff",
            )
        ],
    )
    uecl = f.competition(
        "uecl",
        ["brann", "tromso"],
        format="european",
        european_rounds=[
            f.european_round(
                "playoff",
                entrants=["brann", "tromso"],
                window_start=date(2026, 8, 20),
                window_end=date(2026, 8, 27),
            )
        ],
    )
    windows = resolve_team_cascade("tromso", el, {"el": el, "uecl": uecl})
    assert len(windows) == 2
    assert windows[0].labels == ("el: q3",)
    assert windows[1].window_start == date(2026, 8, 20)
    assert windows[1].window_end == date(2026, 8, 27)


def test_win_and_drop_branches_at_the_same_depth_are_merged_into_one_window():
    """A team that could either advance within its own competition or drop
    into another one's equivalent round has both branches open until a
    result narrows it down — the resolver must block the union, not pick
    one arbitrarily."""
    el = f.competition(
        "el",
        ["tromso"],
        format="european",
        european_rounds=[
            f.european_round(
                "q3",
                entrants=["tromso"],
                window_start=date(2026, 8, 6),
                window_end=date(2026, 8, 9),
                drop_to_competition="uecl",
                drop_to_round="playoff",
            ),
            # Win branch: stays in the Europa League, a slightly later window.
            f.european_round(
                "playoff", entrants=["tromso"], window_start=date(2026, 8, 22), window_end=date(2026, 8, 24)
            ),
        ],
    )
    uecl = f.competition(
        "uecl",
        ["tromso"],
        format="european",
        european_rounds=[
            # Drop branch: an earlier window than the win branch above.
            f.european_round(
                "playoff", entrants=["tromso"], window_start=date(2026, 8, 18), window_end=date(2026, 8, 20)
            )
        ],
    )
    windows = resolve_team_cascade("tromso", el, {"el": el, "uecl": uecl})
    assert len(windows) == 2
    depth1 = windows[1]
    # Union across both branches: earliest start, latest end, both labels.
    assert depth1.window_start == date(2026, 8, 18)
    assert depth1.window_end == date(2026, 8, 24)
    assert set(depth1.labels) == {"el: playoff", "uecl: playoff"}


def test_min_rest_days_at_each_depth_is_the_strictest_of_the_merged_branches():
    el = f.competition(
        "el",
        ["tromso"],
        format="european",
        min_rest_days=3,
        european_rounds=[
            f.european_round(
                "q3", entrants=["tromso"], forced_date=date(2026, 8, 6),
                drop_to_competition="uecl", drop_to_round="playoff",
            ),
            f.european_round("playoff", entrants=["tromso"], forced_date=date(2026, 8, 22)),
        ],
    )
    uecl = f.competition(
        "uecl",
        ["tromso"],
        format="european",
        min_rest_days=6,
        european_rounds=[f.european_round("playoff", entrants=["tromso"], forced_date=date(2026, 8, 18))],
    )
    windows = resolve_team_cascade("tromso", el, {"el": el, "uecl": uecl})
    assert windows[1].min_rest_days == 6


def test_dangling_drop_to_competition_raises():
    comp = f.competition(
        "el",
        ["tromso"],
        format="european",
        european_rounds=[
            f.european_round(
                "q3", entrants=["tromso"], forced_date=date(2026, 8, 6),
                drop_to_competition="ghost", drop_to_round="whatever",
            )
        ],
    )
    with pytest.raises(EuropeanCascadeError, match="unknown competition"):
        resolve_team_cascade("tromso", comp, {"el": comp})


def test_dangling_drop_to_round_raises():
    el = f.competition(
        "el",
        ["tromso"],
        format="european",
        european_rounds=[
            f.european_round(
                "q3", entrants=["tromso"], forced_date=date(2026, 8, 6),
                drop_to_competition="uecl", drop_to_round="ghost_round",
            )
        ],
    )
    uecl = f.competition(
        "uecl", ["brann"], format="european",
        european_rounds=[f.european_round("q2", entrants=["brann"], forced_date=date(2026, 7, 21))],
    )
    with pytest.raises(EuropeanCascadeError, match="does not exist there"):
        resolve_team_cascade("tromso", el, {"el": el, "uecl": uecl})


# -- resolve_european_commitments: season-level orchestration ----------------


def test_resolve_european_commitments_resolves_every_direct_entrant():
    cl = f.competition(
        "cl",
        ["glimt", "viking"],
        format="european",
        european_rounds=[
            f.european_round("q3", entrants=["glimt"], forced_date=date(2026, 8, 4)),
            f.european_round("playoff", entrants=["glimt", "viking"], forced_date=date(2026, 8, 18)),
        ],
    )
    result = resolve_european_commitments([cl])
    assert set(result) == {"glimt", "viking"}
    assert len(result["glimt"]) == 2
    assert len(result["viking"]) == 1


def test_resolve_european_commitments_does_not_double_resolve_a_cascade_landing_spot():
    """`tromso` is a real entrant of `el` and only a cascade landing spot in
    `uecl` — iterating `uecl.teams` must not treat `uecl`'s playoff round as
    a second, independent home for `tromso`, which would silently overwrite
    the correct (two-window) result from `el` with the incomplete
    one-window result starting at the drop target."""
    el = f.competition(
        "el",
        ["tromso"],
        format="european",
        european_rounds=[
            f.european_round(
                "q3", entrants=["tromso"], forced_date=date(2026, 8, 6),
                drop_to_competition="uecl", drop_to_round="playoff",
            )
        ],
    )
    uecl = f.competition(
        "uecl",
        ["brann", "tromso"],
        format="european",
        european_rounds=[
            f.european_round("q2", entrants=["brann"], forced_date=date(2026, 7, 21)),
            f.european_round("playoff", entrants=["brann", "tromso"], forced_date=date(2026, 8, 20)),
        ],
    )
    result = resolve_european_commitments([el, uecl])
    assert len(result["tromso"]) == 2, "tromso's el-then-uecl cascade must survive intact"
    assert len(result["brann"]) == 2
