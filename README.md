# espenhk-hobby-projects

Hobby projects done in my free time.

---

## Projects

### `dataplatform-beta` — Azure Databricks + Foundry Data Platform Example

A repository-in-repository style platform slice that demonstrates medallion ETL, Databricks Asset Bundles, Terraform-based Azure platform wiring, and governed publishing into a Foundry exchange zone.

**Key features:**
- Split sample ETL with explicit raw, bronze, silver, and gold stages
- Databricks Asset Bundle with YAML job orchestration
- Terraform modules for network, storage, Databricks, Foundry, Key Vault, monitoring, Unity Catalog, budgets, and Power BI groups
- Foundry connection contract stored in Key Vault
- Power BI- and Foundry-oriented Gold publishing paths

**State:** Active platform baseline with working sample ETL, bundle/job definition, and supporting architecture/security docs.

```bash
# From the dataplatform-beta directory:
poetry run pytest tests/test_core_nordic_sales_nok.py -q
```

---

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

## Testing

### `dataplatform-beta`

```bash
poetry run pytest dataplatform-beta/tests/ -v
```

### `skate`

```bash
python -m pytest skate/tests/ -v
```

### `tmnf`

The tmnf tests cover all pure-logic components (policies, reward calculation, track
geometry, data structures) and run without the game or TMInterface installed.

```bash
python -m pytest tmnf/tests/ -v
```

Test files are organised one-to-one with their corresponding source files:

| Test file | Covers |
|---|---|
| `test_utils.py` | `Vec3`, `Quat`, `StateData` |
| `test_track.py` | `Centerline` projection |
| `test_simple_policy.py` | `SimplePolicy` |
| `test_weighted_linear_policy.py` | `WeightedLinearPolicy` |
| `test_neural_net_policy.py` | `NeuralNetPolicy` |
| `test_discretize_obs.py` | `_discretize_obs` helper |
| `test_epsilon_greedy_policy.py` | `EpsilonGreedyPolicy` |
| `test_mcts_policy.py` | `MCTSPolicy` |
| `test_genetic_policy.py` | `GeneticPolicy` |
| `test_reward.py` | `RewardCalculator`, `RewardConfig` |

Only `numpy`, `pyyaml`, and `pytest` are required to run the tmnf tests —
none of the game-dependent dependencies (`tminterface`, `pygbx`, etc.) are needed.

---

## Environment Setup

All projects share a single virtual environment managed by [Poetry](https://python-poetry.org/). Python 3.12 is recommended.

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
