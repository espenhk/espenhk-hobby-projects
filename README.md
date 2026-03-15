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

Both projects share a single virtual environment. Python 3.10+ is recommended.

> **Note:** `tminterface` and `pygbx` (required by `tmnf`) are not on PyPI — install them manually from their respective GitHub repos before running `pip install -r requirements.txt`.

### Option A — VS Code (GUI)

1. Open the repo folder in VS Code.
2. Open the Command Palette (`Ctrl+Shift+P`) and run **Python: Create Environment**.
3. Select **Venv**, then select your Python 3.10+ interpreter.
4. When prompted to install dependencies, check `requirements.txt` and confirm.

VS Code will create `.venv/` and install all dependencies automatically. The environment will be selected as the workspace interpreter going forward.

### Option B — CLI

```bash
python -m venv .venv
```

Activate (PowerShell):
```powershell
.venv\Scripts\Activate.ps1
```

Activate (Git Bash / WSL):
```bash
source .venv/Scripts/activate
```

Install dependencies:
```bash
pip install -r requirements.txt
```

Verify:
```bash
python -c "import pandas, numpy, gymnasium; print('OK')"
```
