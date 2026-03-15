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

**State:** Functional — all core features work. Code is a bit rough in places.

Run with:
```bash
python skate/race_predictor.py
```

---

### `tmnf` — Trackmania Nations Forever AI

An attempt at autonomously driving in the racing game Trackmania Nations Forever, first with a hand-tuned PD controller and eventually with a reinforcement learning agent trained via PPO.

**Key features:**
- Centerline-following PD controller (works on track A03)
- Gymnasium-compatible RL environment wrapping the game via TMInterface
- Configurable reward system (weights in `rl/reward_config.yaml`)
- PPO training via `stable-baselines3` with TensorBoard logging
- Thread-safe bridge between TMInterface callbacks and the RL step loop

**State:** RL scaffolding complete, training not yet run end-to-end.

Run adaptive controller:
```bash
python tmnf/main.py
```

Start RL training:
```bash
python tmnf/rl/train.py
```

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
python -c "import pandas, numpy, gymnasium, stable_baselines3; print('OK')"
```
