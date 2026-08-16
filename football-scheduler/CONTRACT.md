# Frontend data contract

This is the documented shape of the data a frontend (currently the plain
HTML report in `football-scheduler-frontend/`, eventually a Lovable-managed
React app in its own repo — see the follow-up issue on converting that
folder to Vite/React/TypeScript) can rely on.

**This is a static, point-in-time export, not a live API.** Nothing in this
project serves HTTP; `write_frontend_json()` is called once per `cli.py
generate`/`export-frontend` run and writes a JSON file. A frontend consuming
it should treat the data as "current as of `generated_at`," not assume it's
always fresh, and never assume the schedule was recomputed on its behalf —
recomputing means running the Python solver, which only happens when someone
runs the CLI.

- **Schema**: [`schemas/season_frontend.schema.json`](schemas/season_frontend.schema.json),
  generated mechanically from the Pydantic models in
  [`terminliste/report/frontend_schema.py`](terminliste/report/frontend_schema.py)
  via `FrontendPayload.model_json_schema()`. That file is the source of truth
  for field names and types — this document only explains what they *mean*.
- **Example**: [`schemas/example_2026.frontend.json`](schemas/example_2026.frontend.json),
  a real, committed export for the 2026 season. Regenerate it after any
  change to the payload shape with:
  ```
  python cli.py export-frontend --season 2026
  cp ../football-scheduler-frontend/data/2026.frontend.json schemas/example_2026.frontend.json
  ```
  (`export-frontend` also commits the fresh fixture straight into the
  frontend project — see its `--help` — the `cp` above is only for updating
  this backend-side reference copy.)

## Top-level shape

`FrontendPayload`: one solve run for one season.

| field | meaning |
|---|---|
| `generated_at` | UTC timestamp of the export — the only signal a frontend has for "how stale is this." |
| `season_id`, `season_year`, `season_start`, `season_end` | the season this schedule is for. |
| `solver` | which solver backend produced it (`local` or `cpsat`) — informational. |
| `club_colors` | `club_id -> hex color`, one entry per **dual club** (a club fielding a team in both leagues). Used to color-code that club's matches consistently across both competitions in the calendar. Clubs not in this map aren't dual clubs and should render neutrally. |
| `options` | 1–3 `FrontendOption`s — different candidate schedules for the same season, ranked by the solver. The reason this is a list at all, rather than one schedule, is the same reason the HTML report has tabs: which candidate to actually use is a judgment call, not something the solver decides unilaterally. |

## `FrontendOption`

One candidate schedule.

| field | meaning |
|---|---|
| `label`, `seed` | identify the candidate (e.g. "Option 1", the solver's random seed). |
| `feasible` | `true` if no hard rule is broken. A frontend showing an infeasible option should say so prominently — it's not usable as-is. |
| `hard_violations` | count of broken hard rules. `0` iff `feasible`. |
| `soft_total` | the schedule's overall soft score — higher is better, no fixed scale (it's a sum of weighted rule contributions, meaningful only relative to the other options in the same payload). |
| `headlines` | 2–3 `{value, label}` pairs — the numbers a reader checks first (e.g. "62% on the preferred weekday"). Display order matters; don't re-sort. |
| `problems`, `upsides` | the biggest negative/positive scoring rules for this option, each `{id, kind, total, count, description, examples, more}` — `examples` are a handful of concrete human-readable instances (e.g. a specific date clash), `more` is how many additional instances exist beyond `examples`. Hard-rule violations always sort to the top of `problems` regardless of point value. |
| `breakdown` | every constraint's contribution, same row shape as `problems`/`upsides` — the full "why this score" table. |
| `competitions` | the actual calendar — see below. |

## `FrontendCompetitionView` / `FrontendRound` / `FrontendMatch`

The calendar, grouped by competition (league) then round.

- `FrontendCompetitionView.preferred_weekday` — the league's preferred
  matchday (e.g. `"sunday"`); not necessarily every match's actual weekday.
- `FrontendRound.dates` — a human-readable label for the round (e.g. `"12
  Apr – 13 Apr"`), already formatted; don't reformat `FrontendMatch.date`
  and expect it to match exactly.
- `FrontendMatch.home` / `.away` — **already-resolved team names**, not ids.
  There's no separate team/club/venue lookup table in this payload —
  everything a UI needs to render a match is inlined here.
- `FrontendMatch.color` / `.away_color` — hex color if the home/away team's
  club is a dual club (matches a key in top-level `club_colors`), else `""`.
- `FrontendMatch.paired` — **the reason this project exists**: `true` if
  this match's home team's club has another home match (either league) on
  an adjacent calendar day. Scheduling the two leagues together specifically
  to produce more of these is the whole point (see the root README) — a
  frontend should visually call this out (the HTML report uses a green
  border and a ◆ marker), not treat it as a minor detail.

## What's deliberately *not* in this payload

- No team/venue ids, no separate lookup tables — names are inlined so the
  frontend never needs to join against `data/*.yml`.
- No live recompute hook, no websocket, no polling endpoint. If a
  "regenerate" feature is ever wanted in the frontend, that's a deliberate,
  separate decision (it would need either a hosted Python service or a
  TypeScript reimplementation of the solver) — not something to assume this
  contract supports.
