# Terminliste — football league season scheduler

Generates a season fixture list for a set of related football leagues,
scores it against a mix of hard rules and soft preferences, and reports the
result as a browsable HTML page. Built around Eliteserien (men) and
Toppserien (women) 2026 — six clubs field a team in both, which is the
coupling this project exists to handle well.

See `/CLAUDE.md` at the repo root for how this project fits alongside the
others sharing this Poetry environment.

## Quickstart

```bash
poetry install                     # or: pip install pydantic pyyaml jinja2 pytest

cd football-scheduler
python cli.py validate                              # data integrity, no solving
python cli.py generate --season 2026                 # solve, write schedules/2026.html
python cli.py score my_schedule.csv --season 2026     # score a real/proposed schedule
python -m pytest ..                                   # -m pytest tests/ from the repo root
```

`generate` defaults to the local-search solver (no extra dependencies).
`--solver cpsat` uses OR-Tools for a near-optimal search — install it with
`poetry install --with football-scheduler-cpsat` (or `pip install ortools`).

## What's here

- **`data/`** — the source of truth: venues, clubs/teams, competitions,
  season calendar (blackouts, fixed requirements), and curated travel-time
  overrides. All YAML, hand-editable. Every file is marked `verified: false`
  because the sandbox this was built in couldn't reach Wikipedia or the
  stats sites — assembled from web search snippets plus general knowledge.
  **Check the rosters, venues and coordinates before using this for
  anything real**; `cli.py validate` only catches referential and
  geometric problems (unknown ids, coordinates outside Norway), not factual
  ones.
- **`terminliste/model/`** — Pydantic schema + loader (`World`), the season
  calendar (blackout resolution, anchor-date selection), and the travel-time
  model.
- **`terminliste/rounds/`** — the circle-method round-robin generator. Pure
  combinatorics, no dates: who plays whom, home or away, is decided here and
  is correct by construction.
- **`terminliste/scoring/`** — the constraint framework. Every rule (hard or
  soft) is an object with an `evaluate()` method; `registry.py` assembles the
  list for a season. Add a rule by writing a class and registering it — both
  solvers and the report pick it up automatically.
- **`terminliste/solvers/`** — two interchangeable backends behind one
  `Scheduler` protocol:
  - `local_search.py` (default): greedy construction + simulated annealing
    over four move operators. No extra dependencies.
  - `cpsat.py` (`--solver cpsat`): OR-Tools CP-SAT, assigning dates to a
    fixed pairing structure. Needs the optional `football-scheduler-cpsat`
    dependency group.
- **`terminliste/report/`** — Jinja2 → one self-contained HTML file. Tabs
  between candidate schedules, a score header, ranked "biggest upsides /
  biggest problems", a full per-rule breakdown table, and a calendar grid
  with dual-club back-to-back home days highlighted.
- **`terminliste/external_schedule.py`** — loads a CSV or JSON schedule from
  anywhere (a real league's published fixtures, a hand-drafted proposal) and
  scores it against the same rules, so `cli.py score` can point out exactly
  what's wrong with a schedule the tool didn't generate.

## Data model

```
Venue     id, name, city, lat/lon, capacity, surface
Team      id, gender, level (senior|second|youth), home_venue, club_id
Club      id, name, teams[]                    # 1+ teams; "dual clubs" have 2+ senior teams
Competition  id, season, gender, format (league|cup), teams[], preferred_weekday, weights{}
             cup_rounds[]                       # cup only: real-world (name, date) per round
Season    id, year, window, competitions[], cup_competitions[], global_blackouts[],
          venue_blackouts[], fixed_requirements[]
Fixture   an unscheduled pairing (home, away, leg, round)         # league only
Match     a Fixture placed on a date at a venue                    # league only
```

`Team.level` is wider than today's use needs on purpose — a reserve side is a
data edit (`level: second`), not a rewrite.

A **league** (`format: league`) is generated and dated by the solver, the way
Eliteserien and Toppserien are. A **cup** (`format: cup`) is the opposite: its
`cup_rounds` are real-world fixed dates the solver treats as given rather than
something to search over — see `data/competitions/cup_men_2027.yml` and
`cup_women_2027.yml` for the 2026-27 Norwegian Cup. A season lists which
competitions of each kind it holds under `competitions` (leagues) and
`cup_competitions` (cups) respectively; the two are kept separate because only
the former is fed to the round-robin/solver pipeline. Since cup pairings are
drawn round by round, `CupRoundConflict` treats every team entered in a cup as
still alive through the final and keeps league fixtures a `min_rest_days`-wide
window clear of every remaining round, rather than modelling actual ties.

## Constraints implemented

**Hard** (`terminliste/scoring/hard.py`) — a schedule with any of these
present is not feasible, full stop:
`min_rest_days`, `blackout_dates`, `venue_double_booking`, `club_home_clash`,
`leg_ordering`, `fixed_requirement`, `one_match_per_team_per_day`,
`cup_round_conflict`.

**Soft** (`terminliste/scoring/soft.py`) — scored, signed (reward positive,
penalty negative), and shown ranked in the report:
`preferred_weekday`, `consecutive_home_days`, `consecutive_away_days` (scaled
by travel time, capped at an 8h default), `home_away_breaks`,
`home_away_balance`, `rest_comfort`, `soft_venue_preference`.

Run `python cli.py score <file> --season 2026` on any schedule to see every
rule's contribution, with named examples for anything that fired.

## Testing

```bash
python -m pytest tests/ -v
```

- `test_round_robin.py` — exhaustive n=2..20 checks on the pairing generator.
- `test_hard_constraints.py` / `test_soft_constraints.py` — each rule at its
  boundary, hand-built 4-team schedules, plus a check that every hard rule is
  silent on a clean schedule.
- `test_calendar.py`, `test_travel.py`, `test_loader.py` — the supporting
  model layer, including curated overrides and referential-integrity errors.
- `test_external_schedule.py` — CSV/JSON parsing, leg inference, coverage
  warnings, and a schedule with deliberate flaws scoring the right hard
  violations.
- `test_solver_contract.py` — parametrized over both backends (`cpsat`
  skipped if OR-Tools isn't installed): diverse top-N candidates, every
  fixture placed once, feasibility achievable, determinism, and a graceful
  report on an unsolvable calendar.
- `test_integration_coupled_leagues.py` — the actual point of this project:
  on the real 2026 data, scheduling the two leagues together produces
  strictly more back-to-back home days for dual clubs than scheduling them
  independently would.

## Suggested next steps

See the write-up delivered alongside this project for the full discussion.
The Norwegian Cup is now in (`cup_men_2027.yml` / `cup_women_2027.yml`,
`CupRoundConflict`) — only the top-flight clubs' rounds are tracked, and only
Round 1 (men) / Round 2 (women) and the "final in spring 2027" framing are
NFF-confirmed; everything after is a placeholder date, flagged per round via
`note`, pending NFF publishing the real ones (see each file's header).
Natural next steps from here: European qualifiers for the tournaments this
project doesn't control the scheduling of (issue #31), and cascading
Champions/Europa/Conference League qualifier progression (issue #29).
