# CLAUDE.md

This repo contains independent hobby projects sharing a single Python virtual environment managed by Poetry.

How this repo fits with the other espenhk repos (Pages, portfolio, skills): [ARCHITECTURE.md](https://github.com/espenhk/espenhk.github.io/blob/main/ARCHITECTURE.md).

---

## Repository Structure

```sh
espenhk-hobby-projects/
├── .venv/                       # Shared virtual environment (created by Poetry)
├── docs/                        # GitHub Pages root — mobile-viewable POC frontends, one folder per project
├── skate/                       # Ice skating race predictor
├── conversational-analytics/    # NL -> semantic model -> DuckDB -> Vega-Lite dashboard prototype
├── pyproject.toml               # Shared dependencies for all projects
├── poetry.lock                  # Locked dependency versions
├── GITHUB_PAGES_SETUP.md        # One-time GitHub Pages setup (do from a phone)
├── README.md
└── CLAUDE.md
```

---

## Project: `skate`

### Purpose

Terminal app for live ice skating race tracking. Operator inputs lap splits as they happen; the app predicts finish times and tracks inter-skater gaps.

### Structure

```sh
skate/
├── race_predictor.py       # Entry point — run this
├── start.py                # Shortcut launcher
├── demo.py                 # Demo with fake data
├── models/
│   ├── skater.py           # Skater state + speed-based prediction
│   ├── race.py             # Race state management
│   ├── competition.py      # Competition + leaderboard
│   ├── person.py           # Skater profile entity
│   └── race_preset.py      # Distance configs (1500m, 3000m, 5000m, 10000m)
├── engine/
│   └── predictor.py        # Algorithms: simple / weighted / fatigue-adjusted
├── ui/
│   ├── cli.py              # Interactive CLI
│   └── base_ui.py          # Base display components
├── presets/                # JSON race distance configs
├── data/
│   ├── competitions/       # Competition fixture JSON files
│   └── people/             # Individual skater profiles (JSON)
├── scripts/
│   ├── parse_pdf.py        # Extract skater lists from PDF start lists
│   ├── manage_persons.py   # CRUD for skater database
│   └── populate_people_from_competition.py
└── tests/
    └── test_race_predictor.py  # Unit tests
```

### State

Complete and functional. All core features work. Skater profiles include historical PB/SB data. PDF parsing script exists for loading real competition start lists.

### Key design decisions

- Predictions use average speed (m/s) rather than raw lap times, which handles variable-distance first laps correctly.
- Time input is flexible: `MM:SS.mmm`, `SS.mmm`, or bare `SS`.
- Data is JSON-based, no database needed.

### Running tests

```bash
python -m pytest skate/tests/
```

---

## Project: `conversational-analytics`

### Purpose

A local, dependency-light prototype proving out a conversational-analytics
architecture (the Microsoft Fabric data-agent pattern, built natively):
a natural-language question about a fictional coffee-shop chain's sales is
grounded in a file-defined semantic model, compiled to DuckDB SQL, executed
against local Parquet, and rendered as a self-contained interactive HTML
dashboard. The LLM (Claude, via the `anthropic` SDK) only ever produces
*structure* — a logical query and Vega-Lite chart encodings — never raw SQL
and never numbers; DuckDB is the sole source of truth for values.

### Structure

```sh
conversational-analytics/
├── semantic_model/       # single source of business meaning: tables, relationships,
│                          # metrics, verified_answers, row_filters — all YAML
├── data/                  # generated Parquet star schema (shipped, runs offline)
├── scripts/generate_data.py
├── fjordroast/
│   ├── semantic/          # loader/validator + query-builder (LogicalQuery -> SQL)
│   ├── agent/              # NL -> LogicalQuery, result -> Vega-Lite spec(s), narrative
│   ├── dashboard/          # Jinja2 HTML assembly + pinned Vega-Lite schema
│   ├── store/              # SQLite "living dashboard" persistence
│   └── server.py           # stretch: FastAPI chat + gallery
├── cli.py                 # ask / validate / refresh / serve
├── tests/
└── dashboards/             # generated dashboard.html files + dashboards.db
```

### State

Complete and functional. `validate` and `refresh` run fully offline against
the shipped data; `ask` and `serve` require `ANTHROPIC_API_KEY`. See
`conversational-analytics/README.md` for the full architecture writeup and
the Fabric-concept mapping table.

### Running tests

```bash
poetry run python -m pytest conversational-analytics/tests/
```

---

## Moved out: football-scheduler

The football league season scheduler now lives in its own repo,
[espenhk/season-scheduler](https://github.com/espenhk/season-scheduler) (#130).

---

## Mobile-viewable POC frontends (`docs/`)

Any project can publish a mobile-viewable POC frontend under `docs/<project-name>/`.
`docs/` is the GitHub Pages publishing root for the whole repo — whatever lands
there is live at `https://espenhk.github.io/espenhk-hobby-projects/<project-name>/`
within about a minute of a merge to `main`.

Full convention, including the "vanilla JS, no build step, CDN dependencies"
rule for hand-written frontends, is in `docs/README.md` — read it before
adding a new project's POC. `docs/discus-analysis/` is the reference
example of a hand-written POC.

One-time GitHub setup (enabling Pages itself) is documented in
`GITHUB_PAGES_SETUP.md` at the repo root, written to be done from a phone.

---

## Dependencies

Managed by Poetry. Run `poetry install` to create `.venv/` and install all dependencies.

---

## Code comments

Comments should be brief and explain *why*, not restate *what* the code
already makes clear through legible naming and structure. A single line is
usually enough to orient a reader; multiline comments are the exception, not
the rule — reserve those for something genuinely intricate that a line
can't carry. Comments should describe the code as it stands now, not the
history of how it got there — don't reference a previous implementation, a
past bug, or a since-changed approach. If it's not needed to understand or
improve the current code, leave it out.

If a *why* traces back to a GitHub issue, note the issue number in
parentheses at the end of the relevant sentence, e.g. `(#42)`, rather than
narrating the issue inline ("issue #42 needed..."). This keeps the comment
itself terse while still giving a reader a thread to pull if they want the
full history.

---

## Git & PR conventions

When a pull request's changes fix one or more GitHub issues, the PR
description must list each one on its own line as `closes #<number>` (or
`fixes #<number>`), e.g.:

```
closes #18
closes #19
closes #21
```

This is what lets GitHub auto-close those issues when the PR merges — do
this whether the PR was opened by a person or by an agent, and whether it
fixes one issue or several.

All PRs are merged using squash-merge to keep the main branch history clean
and linear.