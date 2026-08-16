# espenhk-hobby-projects

Hobby projects done in my free time.

---

## Projects

### `skate` — Ice Skating Race Predictor

A terminal application for live tracking of ice skating race times. Feed in lap splits as they happen and get real-time finish time predictions using speed-based algorithms.

**Key features:**
- Live lap time input for two skaters simultaneously
- Real-time finish time predictions (simple, weighted, fatigue-adjusted)
- Leader tracking and time gap comparison
- Competition management with leaderboards
- Skater profile database with historical data (JSON)
- PDF parsing for competition start lists

**State:** Functional — all core features work.

Skater profiles are named after real professional speed skaters, but the bundled
sample race data (times, laps, positions) is a mix of real results and data made
up for testing — don't treat any of it as an accurate record of a real
competition.

```bash
python skate/race_predictor.py
```

---

### `conversational-analytics` — Conversational Analytics Prototype

A local, dependency-light prototype of a conversational-analytics architecture
(the Microsoft Fabric data-agent pattern, built natively): a natural-language
question about a fictional coffee-shop chain's sales is grounded in a
file-defined semantic model, compiled to DuckDB SQL, executed against local
Parquet, and rendered as a self-contained interactive HTML dashboard. Claude
only ever produces *structure* (a logical query, chart encodings) — DuckDB is
the sole source of truth for numbers.

**State:** Functional. `validate` and `refresh` run fully offline; `ask` and
`serve` need `ANTHROPIC_API_KEY`. See
[`conversational-analytics/README.md`](conversational-analytics/README.md)
for the full architecture writeup.

```bash
poetry run python conversational-analytics/cli.py validate
```

---

### `football-scheduler` — Football League Season Scheduler

Generates a season fixture list for coupled Norwegian football leagues
(Eliteserien and Toppserien), scores it against hard rules and soft
preferences, and reports the result as a browsable HTML page.

**State:** Functional first version, runs fully offline. Club/venue/travel-time
data in `football-scheduler/data/` is marked `verified: false` throughout —
it was assembled from web search rather than a fetchable source, not fact-checked,
and shouldn't be relied on as accurate. See
[`football-scheduler/README.md`](football-scheduler/README.md) for the full
writeup and constraint list.

```bash
poetry run python football-scheduler/cli.py generate
```

---

#### Testing

```bash
python -m pytest skate/tests/ -v
poetry run python -m pytest conversational-analytics/tests/
poetry run python -m pytest football-scheduler/tests/
```

## Environment Setup

All projects share a single virtual environment managed by [Poetry](https://python-poetry.org/). Python 3.12 is recommended.

### Install Poetry

```bash
curl -sSL https://install.python-poetry.org | python3 -
```

Then ensure `~/.local/bin` is on your PATH (add to `~/.bashrc` to make it permanent):

```bash
export PATH="$HOME/.local/bin:$PATH"
```

### Install dependencies

```bash
# Create .venv/ inside the project (recommended)
poetry config virtualenvs.in-project true

poetry install
```

### VS Code integration

After running `poetry install`, point VS Code at the local venv:

- Open the Command Palette (`Ctrl+Shift+P`) → **Python: Select Interpreter**
- Choose `./.venv/bin/python`

Or set it permanently in `.vscode/settings.json`:

```json
{
    "python.defaultInterpreterPath": "${workspaceFolder}/.venv/bin/python"
}
```

### Running commands

```bash
poetry run python skate/race_predictor.py

# Or activate the venv in your shell first:
poetry shell
```

### Adding / removing dependencies

```bash
poetry add <package>
poetry remove <package>
```

Both `pyproject.toml` and `poetry.lock` should be committed — the lockfile ensures everyone gets the exact same dependency versions.
