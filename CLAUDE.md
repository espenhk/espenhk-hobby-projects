# CLAUDE.md

This repo contains independent hobby projects sharing a single Python virtual environment managed by Poetry.

---

## Repository Structure

```sh
espenhk-hobby-projects/
├── .venv/                       # Shared virtual environment (created by Poetry)
├── docs/                        # GitHub Pages root — mobile-viewable POC frontends, one folder per project
├── skate/                       # Ice skating race predictor
├── conversational-analytics/    # NL -> semantic model -> DuckDB -> Vega-Lite dashboard prototype
├── football-scheduler/          # Football league season scheduler (terminliste)
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

## Project: `football-scheduler`

### Purpose

Generates a season fixture list for a set of related football leagues,
scores it against hard rules and soft preferences, and reports the result as
a browsable HTML page. Built around the Norwegian Eliteserien (men, 16 clubs)
and Toppserien (women, 12 clubs) for 2026 — six clubs field a team in both,
and scheduling the two leagues together so those pairs get back-to-back home
weekends (rather than clashing, or scheduled independently) is the reason
this project exists rather than a generic single-league scheduler.

### Structure

```sh
football-scheduler/
├── data/                   # source of truth: venues, clubs/teams, competitions,
│                            # season calendar, curated travel-time overrides — all YAML
├── cli.py                  # validate / generate / score / explain
├── terminliste/
│   ├── model/               # Pydantic schema + loader (World), calendar, travel model
│   ├── rounds/               # circle-method round-robin pairing generator
│   ├── scoring/               # constraint framework: hard.py, soft.py, registry.py
│   ├── solvers/                # local-search (default) and CP-SAT (--solver cpsat) backends
│   ├── report/                  # Jinja2 -> self-contained HTML season report
│   └── external_schedule.py      # score a real/proposed CSV or JSON schedule
├── scripts/
│   └── publish_web.py       # generate + publish the report to docs/football-scheduler/
├── schedules/                # generated HTML + JSON output (gitignored)
└── tests/
```

### State

Complete and functional first version. `validate`, `generate` (local solver),
and `score` all run fully offline with no external dependencies beyond
`pydantic`/`pyyaml`/`jinja2`. `--solver cpsat` needs the optional
`football-scheduler-cpsat` Poetry group (OR-Tools). Club/venue data in
`data/` is marked `verified: false` — assembled from web search rather than a
fetchable source, so check it before relying on it for anything real. See
`football-scheduler/README.md` for the full architecture writeup, the
constraint list, and suggested next steps (Norwegian Cup before European
qualifiers, plus a handful of scoring rules the current set is missing).
The season report is also published as a mobile-viewable POC — see
`scripts/publish_web.py` and the "Mobile-viewable POC frontends" section
above.

### Running tests

```bash
poetry run python -m pytest football-scheduler/tests/
```

---

## Mobile-viewable POC frontends (`docs/`)

Any project can publish a mobile-viewable POC frontend under `docs/<project-name>/`.
`docs/` is the GitHub Pages publishing root for the whole repo — whatever lands
there is live at `https://espenhk.github.io/espenhk-hobby-projects/<project-name>/`
within about a minute of a merge to `main`.

Full convention, including the "vanilla JS, no build step, CDN dependencies"
rule for hand-written frontends, is in `docs/README.md` — read it before
adding a new project's POC. `football-scheduler/scripts/publish_web.py` is
the reference example (publishes an already-self-contained generated HTML
report rather than writing new frontend code).

One-time GitHub setup (enabling Pages itself) is documented in
`GITHUB_PAGES_SETUP.md` at the repo root, written to be done from a phone.

---

## Dependencies

Managed by Poetry. Run `poetry install` to create `.venv/` and install all dependencies.