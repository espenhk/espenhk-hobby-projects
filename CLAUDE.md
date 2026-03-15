# CLAUDE.md

This repo contains two independent hobby projects sharing a single Python virtual environment (`.venv/`).

---

## Repository Structure

```
espenhk-hobby-projects/
├── .venv/                  # Shared virtual environment
├── skate/                  # Ice skating race predictor
├── tmnf/                   # Trackmania Nations Forever AI
├── requirements.txt        # Shared dependencies for both projects
├── README.md
└── CLAUDE.md
```

---

## Project: `skate`

### Purpose
Terminal app for live ice skating race tracking. Operator inputs lap splits as they happen; the app predicts finish times and tracks inter-skater gaps.

### Structure
```
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
│   ├── competitions/       # Competition fixture JSON files (3 competitions)
│   └── people/             # Individual skater profiles (28 JSON files)
├── scripts/
│   ├── parse_pdf.py        # Extract skater lists from PDF start lists
│   ├── manage_persons.py   # CRUD for skater database
│   └── populate_people_from_competition.py
└── tests/
    └── test_race_predictor.py  # 11 unit tests
```

### State
Complete and functional. All core features work. Skater profiles include historical PB/SB data. PDF parsing script exists for loading real competition start lists.

#### Key design decisions
- Predictions use average speed (m/s) rather than raw lap times, which handles variable-distance first laps correctly.
- Time input is flexible: `MM:SS.mmm`, `SS.mmm`, or bare `SS`.
- Data is JSON-based, no database needed.

---

## Project: `tmnf`

### Purpose
Drive in Trackmania Nations Forever autonomously — first with a hand-coded PD controller, then with a reinforcement learning agent.

### Structure
```
tmnf/
├── main.py                 # Entry point — switches between adaptive/RL modes
├── utils.py                # StateData, Vec3, Quat, WheelState data classes
├── track.py                # Centerline class: load .npy, project position
├── build_centerline.py     # Script to build centerline from a replay
├── instructions.py         # Predefined input instruction sequences
├── clients/
│   ├── phase.py            # Phase enum (BRAKING_START, RUNNING)
│   ├── instruction_client.py  # Replays a fixed instruction sequence
│   ├── adaptive_client.py  # PD controller following centerline (works on A03)
│   └── rl_client.py        # Thread-safe bridge for RL training
├── rl/
│   ├── env.py              # TMNFEnv — Gymnasium Env wrapping the game
│   ├── reward.py           # RewardCalculator + RewardConfig
│   ├── reward_config.yaml  # Reward weights (edit without touching code)
│   ├── train.py            # PPO training script
│   └── __init__.py
├── replays/
│   └── a03_centerline.Replay.Gbx   # Source replay for centerline
└── tracks/
    └── a03_centerline.npy           # Precomputed centerline array
```

### State
RL scaffolding is complete but training has not been run end-to-end yet. The adaptive client works on track A03. The RL environment, reward system, and training script are wired up and ready to run.

### RL environment details

**Observation (15 floats):**
| Index | Name | Description |
|-------|------|-------------|
| 0 | speed_ms | Speed in m/s |
| 1 | lateral_offset_m | Metres from centreline |
| 2 | vertical_offset_m | Height above/below centreline |
| 3 | yaw_error_rad | Heading vs track direction |
| 4–5 | pitch_rad, roll_rad | Car body angles |
| 6 | track_progress | [0, 1] along track |
| 7 | turning_rate | |
| 8–11 | wheel contacts | 4 wheels (bool as float) |
| 12–14 | angular_velocity | x, y, z |

**Action space:** Discrete(9) — combinations of {brake, coast, accel} × {left, straight, right}

**Termination:**
- Finished: `track_progress >= 1.0`
- Crashed: `|lateral_offset| > 10 m`
- Truncated: timeout (`> 120 s`) or hard crash (`> 50 m`)

**Reward components** (weights in `rl/reward_config.yaml`):
- Progress reward (primary driving signal)
- Centerline penalty (quadratic in lateral offset)
- Speed bonus (small, breaks ties)
- Per-step time penalty (encourages finishing fast)
- Finish bonus + finish time bonus/penalty
- Airborne penalty

### Threading model
TMInterface is callback-driven (`on_run_step`); the RL loop is step-driven (`env.step()`). `RLClient` bridges these with a thread-safe action queue + state queue, so one game tick = one RL step.

### Key design decisions
- Reward weights live in YAML so they can be tuned without touching code.
- Game speed can be set above 1× during training for faster data collection.
- Adaptive client uses three steering terms (lateral P, lateral-velocity D, heading feedforward) — a good baseline to compare RL against.

---

## Dependencies

All in `requirements.txt`. Run `pip install -r requirements.txt` inside the `.venv`.

`tminterface` and `pygbx` are not on PyPI — install from source before running pip if needed.

## Running tests

```bash
python -m pytest skate/tests/
```
