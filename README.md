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

```bash
python skate/race_predictor.py
```

---

### `tmnf` — Trackmania Nations Forever AI

Autonomous driving in Trackmania Nations Forever. Implements a hand-tuned PD controller as a baseline, then trains a linear policy via hill-climbing against a live game environment.

**Key features:**
- Centerline-following PD controller (works on track A03)
- Gymnasium-compatible RL environment wrapping the game via TMInterface
- Hill-climb training with random-restart cold-start and greedy optimisation phases
- Per-experiment isolation: each run gets its own weights and reward config in `experiments/<name>/`
- Reward system fully configurable via YAML — no code changes needed to tune
- Thread-safe bridge between TMInterface callbacks and the RL step loop

**State:** Training loop is fully operational. The hill-climb approach is functional; PPO/SB3 scaffolding exists but is not the primary training path.

```bash
# From the tmnf/ directory:
python main.py <experiment_name>
```

On first run with a new experiment name, a fresh reward config is copied from `rl/reward_config.yaml` into `experiments/<experiment_name>/`. Edit that file to tune rewards for that experiment without affecting others.

---

## Environment Setup

Both projects share a single virtual environment managed by [Poetry](https://python-poetry.org/). Python 3.12 is recommended.

> **Note:** `tminterface` and `pygbx` (required by `tmnf`) are not on PyPI — install them manually from their respective GitHub repos before running `poetry install`.

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
poetry run python tmnf/main.py <experiment_name>

# Or activate the venv in your shell first:
poetry shell
```

### Adding / removing dependencies

```bash
poetry add <package>
poetry remove <package>
```

Both `pyproject.toml` and `poetry.lock` should be committed — the lockfile ensures everyone gets the exact same dependency versions.
