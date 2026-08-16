"""Travel time model: ground-cache lookup, air fallback, override precedence."""

from __future__ import annotations

import json
import math
import time

from terminliste.model.travel import (
    AIR_OVERHEAD_HOURS,
    ApiTravelModel,
    UNTRAVELABLE_THRESHOLD_HOURS,
    great_circle_km,
)


def test_self_distance_is_zero(travel, world):
    venue = next(iter(world.venues))
    assert travel.hours(venue, venue) == 0.0


def test_travel_is_symmetric(travel, world):
    venues = list(world.venues)
    a, b = venues[0], venues[1]
    assert travel.hours(a, b) == travel.hours(b, a)


def test_oslo_bergen_great_circle_is_roughly_right(world):
    """Sanity-check the great-circle helper itself (used for the air-travel
    estimate); Oslo-Bergen is ~305km as the crow flies."""
    intility = world.venue("intility_arena")
    brann = world.venue("brann_stadion")
    km = great_circle_km(intility, brann)
    assert 280 <= km <= 330


def test_override_takes_precedence_over_ground_cache_and_air(world):
    travel = ApiTravelModel(world)
    # travel_overrides.yml sets Bergen-Oslo to 7.5h by train; the air-travel
    # estimate for this distance is much smaller and would win the min()
    # if the override didn't take precedence.
    overridden = travel.hours("brann_stadion", "intility_arena")
    assert overridden == 7.5


def test_null_override_means_unreachable(world):
    travel = ApiTravelModel(world)
    hours = travel.hours("romssa_arena", "intility_arena")
    assert math.isinf(hours)


def test_uncovered_nearby_pair_falls_back_to_air_estimate(world):
    """No override and (in this environment) no fetched ground time — the
    only data available is the flight estimate, dominated by its fixed
    overhead even for a short hop."""
    travel = ApiTravelModel(world)
    hours = travel.hours("kfum_arena", "intility_arena")
    assert AIR_OVERHEAD_HOURS <= hours < AIR_OVERHEAD_HOURS + 1.0


def test_uncovered_distant_pair_gets_a_sensible_flight_estimate(world):
    """Trondheim-Stavanger has no curated override; without a cached ground
    route, the model should still report a finite, reachable flight time
    rather than treating the pair as unreachable."""
    travel = ApiTravelModel(world)
    hours = travel.hours("lerkendal_stadion", "sr_bank_arena")
    assert math.isfinite(hours)
    assert hours < UNTRAVELABLE_THRESHOLD_HOURS


def test_ground_cache_hit_wins_when_faster_than_flying(world, tmp_path):
    cache_path = tmp_path / "travel.json"
    cache_path.write_text(
        json.dumps(
            {
                "fetched_at": time.time(),
                "payload": {"intility_arena|kfum_arena": {"duration_hours": 0.3, "distance_km": 12.0}},
            }
        )
    )
    travel = ApiTravelModel(world, ground_cache_path=cache_path)
    assert travel.hours("kfum_arena", "intility_arena") == 0.3


def test_estimate_exposes_both_ground_and_air_hours(world):
    travel = ApiTravelModel(world)
    estimate = travel.estimate("kfum_arena", "intility_arena")
    assert estimate.ground_hours is None
    assert estimate.air_hours == travel.hours("kfum_arena", "intility_arena")
    assert not estimate.unreachable


def test_unreachable_when_both_ground_and_air_exceed_threshold(world):
    travel = ApiTravelModel(world, threshold_hours=0.01)
    estimate = travel.estimate("kfum_arena", "intility_arena")
    assert estimate.unreachable
    assert math.isinf(travel.hours("kfum_arena", "intility_arena"))
