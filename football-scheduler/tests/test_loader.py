"""Referential-integrity checks on the shipped data files."""

from __future__ import annotations

from datetime import date

import pytest

from terminliste.model.loader import DataError, validate_world
from terminliste.model.schema import FixedRequirement


def test_shipped_data_loads_and_validates_clean(world):
    assert validate_world(world) == []


def test_eliteserien_and_toppserien_are_present(world):
    assert "eliteserien_2026" in world.competitions
    assert "toppserien_2026" in world.competitions
    assert world.competition("eliteserien_2026").team_count == 16
    assert world.competition("toppserien_2026").team_count == 12


def test_every_team_home_venue_resolves(world):
    for team in world.teams.values():
        assert team.home_venue in world.venues


def test_dual_clubs_have_matching_gender_pairs(world):
    for club in world.dual_clubs():
        genders = {t.gender for t in club.teams if t.level == "senior"}
        assert genders == {"men", "women"}, club.id


def test_unknown_team_in_competition_is_caught():
    import factories as f

    v = f.venue("v1")
    t1 = f.team("t1", "c1", "v1")
    clubs = [f.club("c1", [t1])]
    comp = f.competition("comp", ["t1", "ghost_team"])
    bad_world = f.world(clubs, [v], [comp])
    errors = validate_world(bad_world)
    assert any("ghost_team" in e for e in errors)


def test_wrong_gender_team_in_competition_is_caught():
    import factories as f

    v = f.venue("v1")
    t1 = f.team("t1", "c1", "v1", gender="women")
    clubs = [f.club("c1", [t1])]
    comp = f.competition("comp", ["t1"], gender="men")
    bad_world = f.world(clubs, [v], [comp])
    errors = validate_world(bad_world)
    assert any("t1" in e and "women" in e for e in errors)


def test_hard_requirement_on_a_blackout_date_is_caught():
    from terminliste.model.loader import _validate_fixed_requirements
    import factories as f

    v = f.venue("v1")
    t1 = f.team("t1", "c1", "v1")
    t2 = f.team("t2", "c2", "v1")
    clubs = [f.club("c1", [t1]), f.club("c2", [t2])]
    comp = f.competition("comp", ["t1", "t2"])
    bad_world = f.world(clubs, [v], [comp])
    from terminliste.model.schema import DatedNote

    clash_date = date(2026, 5, 17)
    requirement = FixedRequirement(
        id="req", date=clash_date, home_team="t1", competition="comp", hard=True
    )
    season = f.season(
        competitions=["comp"],
        global_blackouts=[DatedNote(date=clash_date, reason="holiday")],
        fixed_requirements=[requirement],
    )
    errors = _validate_fixed_requirements(bad_world, season)
    assert any("blackout" in e for e in errors)


def test_season_shorter_than_required_rounds_is_caught():
    from terminliste.model.loader import _validate_calendar_capacity
    import factories as f

    v = f.venue("v1")
    teams = [f.team(f"t{i}", f"c{i}", "v1") for i in range(8)]
    clubs = [f.club(f"c{i}", [teams[i]]) for i in range(8)]
    comp = f.competition("comp", [t.id for t in teams], min_rest_days=7, rounds_per_pairing=2)
    bad_world = f.world(clubs, [v], [comp])
    tiny_season = f.season(
        competitions=["comp"], start=date(2026, 1, 1), end=date(2026, 1, 31)
    )
    errors = _validate_calendar_capacity(bad_world, tiny_season)
    assert errors


def test_cup_competitions_are_present_and_shaped_correctly(world):
    for cup_id, team_count in (("cup_men_2027", 16), ("cup_women_2027", 12)):
        cup = world.competition(cup_id)
        assert cup.format == "cup"
        assert cup.team_count == team_count
        assert len(cup.cup_rounds) > 0
        dates = [r.date for r in cup.cup_rounds]
        assert dates == sorted(dates), f"{cup_id} rounds are not in date order"

    season = world.season("2026")
    assert set(season.cup_competitions) == {"cup_men_2027", "cup_women_2027"}


def test_cup_with_no_rounds_is_caught():
    import factories as f

    v = f.venue("v1")
    t1 = f.team("t1", "c1", "v1")
    clubs = [f.club("c1", [t1])]
    cup = f.competition("cup", ["t1"], format="cup")
    bad_world = f.world(clubs, [v], [cup])
    errors = validate_world(bad_world)
    assert any("cup" in e and "no cup_rounds" in e for e in errors)


def test_cup_round_dates_out_of_order_are_caught():
    import factories as f

    v = f.venue("v1")
    t1 = f.team("t1", "c1", "v1")
    clubs = [f.club("c1", [t1])]
    cup = f.competition(
        "cup",
        ["t1"],
        format="cup",
        cup_rounds=[
            f.cup_round("r1", date(2026, 9, 1), "Round 1"),
            f.cup_round("r2", date(2026, 8, 1), "Round 2"),
        ],
    )
    bad_world = f.world(clubs, [v], [cup])
    errors = validate_world(bad_world)
    assert any("does not come after the previous round" in e for e in errors)


def test_cup_round_duplicate_ids_are_caught():
    import factories as f

    v = f.venue("v1")
    t1 = f.team("t1", "c1", "v1")
    clubs = [f.club("c1", [t1])]
    cup = f.competition(
        "cup",
        ["t1"],
        format="cup",
        cup_rounds=[
            f.cup_round("r1", date(2026, 8, 1), "Round 1"),
            f.cup_round("r1", date(2026, 9, 1), "Round 2"),
        ],
    )
    bad_world = f.world(clubs, [v], [cup])
    errors = validate_world(bad_world)
    assert any("duplicate cup round id" in e for e in errors)


def test_season_competitions_rejects_a_cup_and_cup_competitions_rejects_a_league():
    import factories as f

    v = f.venue("v1")
    t1 = f.team("t1", "c1", "v1")
    clubs = [f.club("c1", [t1])]
    league = f.competition("league", ["t1"])
    cup = f.competition(
        "cup", ["t1"], format="cup", cup_rounds=[f.cup_round("r1", date(2026, 8, 1))]
    )
    bad_world = f.world(clubs, [v], [league, cup])

    mixed_up = f.season(competitions=["cup"], cup_competitions=["league"])
    bad_world.seasons[mixed_up.id] = mixed_up
    errors = validate_world(bad_world)
    assert any("cups belong under cup_competitions" in e for e in errors)
    assert any("leagues belong under competitions" in e for e in errors)


def test_capacity_check_uses_a_tight_lower_bound_not_rounds_times_rest():
    """A season with just enough room for `(rounds - 1) * min_rest_days + 1`
    days should validate clean — the first round needs no rest before it, so
    only the gaps *between* rounds count. The old `rounds * min_rest_days`
    formula overcounted by one full gap and would wrongly flag this season as
    too short."""
    from terminliste.model.loader import _validate_calendar_capacity
    import factories as f

    v = f.venue("v1")
    teams = [f.team(f"t{i}", f"c{i}", "v1") for i in range(6)]
    clubs = [f.club(f"c{i}", [teams[i]]) for i in range(6)]
    # 6 teams, single league -> 5 rounds. Tight bound: (5-1)*10 + 1 = 41 days.
    comp = f.competition("comp", [t.id for t in teams], min_rest_days=10, rounds_per_pairing=1)
    assert comp.rounds == 5
    world = f.world(clubs, [v], [comp])
    season = f.season(
        competitions=["comp"], start=date(2026, 1, 1), end=date(2026, 2, 10)  # 41 days
    )
    errors = _validate_calendar_capacity(world, season)
    assert errors == []
