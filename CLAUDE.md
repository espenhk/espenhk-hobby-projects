# CLAUDE.md

This repo contains two independent hobby projects sharing a single Python virtual environment managed by Poetry.

---

## Repository Structure

```sh
espenhk-hobby-projects/
├── .venv/                  # Shared virtual environment (created by Poetry)
├── skate/                  # Ice skating race predictor
├── tmnf/                   # Trackmania Nations Forever AI
├── pyproject.toml          # Shared dependencies for both projects
├── poetry.lock             # Locked dependency versions
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

## Dependencies

Managed by Poetry. Run `poetry install` to create `.venv/` and install all dependencies.