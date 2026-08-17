"""Resolves each Norwegian entrant's UEFA qualifying cascade to blocked windows.

Built for issue #29 (modelling the Champions/Europa/Conference League
qualifying cascade) and issue #32 (conditional fixtures whose outcome is not
yet known). A cup round's opponent is unknown but its *place in the
competition* is guaranteed — every entered team is assumed to reach the
final (see `rounds/cup_schedule.py`). A European qualifying round is the
opposite: the opponent is known (UEFA draws pairings well ahead of the tie),
but whether the team is even still in *this* round, rather than having
dropped into a different competition's equivalent round after losing the one
before, is exactly what is not known.

Rather than pick a branch and risk being wrong, this resolves every branch
reachable from a team's entry point and blocks the *union* of their windows.
This is a deliberate simplification, not a limitation: UEFA schedules a
qualifying "stage" — Q1, Q2, Q3, play-offs — within the same week or two
across all three competitions, specifically so a team dropping from the
Champions League into the Europa League (or the Europa League into the
Conference League) keeps playing roughly on schedule rather than getting an
extra rest week for losing. That means the *set of dates a team might be
required to play* at a given cascade depth is well defined even before the
result is known — it just isn't known which of the reachable rounds it will
be. See `EuropeanCommitmentWindow` for exactly what gets merged.

Resolving a real result, once known, is a data edit: delete the
`EuropeanRound` on the branch not taken (or narrow the surviving one's
window to a `forced_date` if it wasn't already exact) and regenerate — the
domestic solver picks up the narrower constraint on the next run, reshuffling
any movable fixture that now conflicts. That is issue #32's "harder case"
(a conditional fixture whose date, once triggered, is fixed and
non-reschedulable forcing other fixtures to move) — no new mechanism is
needed for it beyond what `forced_date` and a solver re-run already do.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from ..model.schema import Competition, EuropeanRound


class EuropeanCascadeError(Exception):
    """A team's European cascade cannot be resolved — a data problem (an
    entrant missing from every round of its own competition, or a
    `drop_to_round` with no matching round in the target competition), not
    something a solver retry can fix."""


@dataclass(frozen=True)
class EuropeanCommitmentWindow:
    """One cascade depth for one team, resolved to a single blocked range.

    `depth` counts qualifying stages from the team's entry point (0 = the
    round it enters at). `labels` names every round merged into this
    window — usually one, but two once a team's fate could plausibly be
    either "won this round, plays the next one" or "lost it, dropped into
    the competition below" and both are still open.
    """

    team_id: str
    depth: int
    window_start: date
    window_end: date
    min_rest_days: int
    labels: tuple[str, ...]


def resolve_team_cascade(
    team_id: str,
    home_competition: Competition,
    competitions_by_id: dict[str, Competition],
) -> list[EuropeanCommitmentWindow]:
    """Every window `team_id` might play in, starting from its entry round
    in `home_competition`.

    Walks forward through two kinds of edge: win-progression (the next
    round in `home_competition.european_rounds`, if `team_id` is one of its
    entrants — advancing without ever consulting `drop_to_*`, since staying
    in the same competition needs no cascade pointer) and elimination
    (`drop_to_competition`/`drop_to_round`, when set). Both are followed at
    once — the walk does not know, and does not need to know, which one is
    real — and their windows at the same depth are merged into one
    conservative range by `_merge_frontier`.
    """
    entry = _entry_round(team_id, home_competition)
    if entry is None:
        raise EuropeanCascadeError(
            f"{team_id!r} is not an entrant of any round in {home_competition.id!r}"
        )

    windows: list[EuropeanCommitmentWindow] = []
    frontier: list[tuple[Competition, EuropeanRound]] = [(home_competition, entry)]
    seen: set[tuple[str, str]] = set()
    depth = 0

    while frontier:
        frontier = [(c, r) for c, r in frontier if (c.id, r.id) not in seen]
        if not frontier:
            break
        seen.update((c.id, r.id) for c, r in frontier)
        windows.append(_merge_frontier(team_id, depth, frontier))

        next_frontier: list[tuple[Competition, EuropeanRound]] = []
        for competition, round_ in frontier:
            win_next = _next_round_for_team(team_id, competition, round_)
            if win_next is not None:
                next_frontier.append((competition, win_next))
            if round_.drop_to_competition is not None:
                drop_competition = competitions_by_id.get(round_.drop_to_competition)
                if drop_competition is None:
                    raise EuropeanCascadeError(
                        f"{competition.id!r} round {round_.id!r} drops into unknown "
                        f"competition {round_.drop_to_competition!r}"
                    )
                drop_round = _round_by_id(drop_competition, round_.drop_to_round)
                if drop_round is None:
                    raise EuropeanCascadeError(
                        f"{competition.id!r} round {round_.id!r} drops into "
                        f"{round_.drop_to_competition!r} round {round_.drop_to_round!r}, "
                        f"which does not exist there"
                    )
                next_frontier.append((drop_competition, drop_round))
        frontier = next_frontier
        depth += 1

    return windows


def _merge_frontier(
    team_id: str, depth: int, frontier: list[tuple[Competition, EuropeanRound]]
) -> EuropeanCommitmentWindow:
    return EuropeanCommitmentWindow(
        team_id=team_id,
        depth=depth,
        window_start=min(r.earliest for _, r in frontier),
        window_end=max(r.latest for _, r in frontier),
        min_rest_days=max(c.min_rest_days for c, _ in frontier),
        labels=tuple(f"{c.name}: {r.name}" for c, r in frontier),
    )


def _entry_round(team_id: str, competition: Competition) -> EuropeanRound | None:
    for round_ in competition.european_rounds:
        if team_id in round_.entrants:
            return round_
    return None


def _round_by_id(competition: Competition, round_id: str | None) -> EuropeanRound | None:
    return next((r for r in competition.european_rounds if r.id == round_id), None)


def _next_round_for_team(
    team_id: str, competition: Competition, round_: EuropeanRound
) -> EuropeanRound | None:
    rounds = competition.european_rounds
    index = next(i for i, r in enumerate(rounds) if r.id == round_.id)
    if index + 1 >= len(rounds):
        return None
    following = rounds[index + 1]
    return following if team_id in following.entrants else None


def resolve_european_commitments(
    competitions: list[Competition],
) -> dict[str, list[EuropeanCommitmentWindow]]:
    """Resolve every team's cascade across every European competition given.

    `competitions` should be every `format == "european"` competition in
    the season, so a `drop_to_competition` pointer always has somewhere to
    resolve to. Only a team's *true* entry competition is walked from: a
    round that is itself the target of some other round's
    `drop_to_competition`/`drop_to_round` is reached by that cascade walk,
    not treated as a second, independent home — starting from both would
    silently overwrite the correct (longer) window list with the
    incomplete one from the cascade's midpoint.
    """
    drop_targets = {
        (round_.drop_to_competition, round_.drop_to_round)
        for competition in competitions
        for round_ in competition.european_rounds
        if round_.drop_to_competition is not None
    }
    by_id = {c.id: c for c in competitions}

    windows_by_team: dict[str, list[EuropeanCommitmentWindow]] = {}
    for competition in competitions:
        for team_id in competition.teams:
            entry = _entry_round(team_id, competition)
            if entry is None:
                continue
            if (competition.id, entry.id) in drop_targets:
                continue
            windows_by_team[team_id] = resolve_team_cascade(team_id, competition, by_id)
    return windows_by_team


def european_conflict(
    windows_by_team: dict[str, list[EuropeanCommitmentWindow]], team_id: str, day: date
) -> bool:
    """Whether `day` falls inside (or too close to) one of `team_id`'s
    resolved European commitment windows.

    `cup_conflict`'s counterpart for range-based windows rather than single
    dates — shared by `solvers/greedy.py`'s construction heuristic (steering
    initial placement away from a European window, the same way it already
    does for `cup_conflict`) and, ultimately, by `EuropeanCommitmentConflict`
    in `scoring/hard.py`, which is the authoritative check a schedule is
    actually judged against.
    """
    for window in windows_by_team.get(team_id, ()):
        if day < window.window_start:
            gap = (window.window_start - day).days
        elif day > window.window_end:
            gap = (day - window.window_end).days
        else:
            return True
        if gap < window.min_rest_days:
            return True
    return False


__all__ = [
    "EuropeanCascadeError",
    "EuropeanCommitmentWindow",
    "european_conflict",
    "resolve_european_commitments",
    "resolve_team_cascade",
]
