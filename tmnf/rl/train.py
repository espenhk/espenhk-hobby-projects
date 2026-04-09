"""
PPO training script for TMNF.

Run from the tmnf/ directory:
    python rl/train.py

Output:
    runs/checkpoints/   — model snapshots every CHECKPOINT_FREQ steps
    runs/tb_logs/       — TensorBoard logs  (tensorboard --logdir runs/tb_logs)
    runs/best_model.zip — saved on clean exit

Tweaking tips
-------------
- Reward weights:    edit config/reward_config.yaml, no code change needed.
- Game speed:        increase SPEED (physics may get unstable above ~20).
- Training length:   increase TOTAL_TIMESTEPS.
- Network size:      change net_arch below (default [64, 64]).
- Sample efficiency: try SAC instead of PPO (swap the import + constructor).
"""

from __future__ import annotations

import os
import sys

# Ensure tmnf/ is on the path regardless of where the script is invoked from.
_TMNF_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _TMNF_DIR not in sys.path:
    sys.path.insert(0, _TMNF_DIR)

from stable_baselines3 import PPO
from stable_baselines3.common.callbacks import CheckpointCallback
from stable_baselines3.common.monitor import Monitor

from rl.env import make_env


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
EXPERIMENT_DIR   = "experiments/ppo_default"
CENTERLINE_FILE  = os.environ.get("TMNF_TRACK", "tracks/a03_centerline.npy")
SPEED            = 10.0      # game speed multiplier
IN_GAME_EPISODE_S = 20.0     # in-game seconds per episode
TOTAL_TIMESTEPS  = 500_000
CHECKPOINT_FREQ  = 5_000     # save a checkpoint every N steps

RUNS_DIR         = "runs"
CHECKPOINT_DIR   = os.path.join(RUNS_DIR, "checkpoints")
TB_LOG_DIR       = os.path.join(RUNS_DIR, "tb_logs")
BEST_MODEL_PATH  = os.path.join(RUNS_DIR, "best_model")


def main() -> None:
    os.makedirs(CHECKPOINT_DIR, exist_ok=True)
    os.makedirs(TB_LOG_DIR, exist_ok=True)

    env = make_env(
        experiment_dir=EXPERIMENT_DIR,
        speed=SPEED,
        in_game_episode_s=IN_GAME_EPISODE_S,
    )
    # Monitor wraps the env to log episode rewards/lengths automatically.
    env = Monitor(env, filename=os.path.join(RUNS_DIR, "monitor.csv"))

    model = PPO(
        policy="MlpPolicy",
        env=env,
        # Collect 512 steps per rollout before updating.
        # Smaller than default (2048) because episodes may be short early in training.
        n_steps=512,
        batch_size=64,
        n_epochs=4,
        learning_rate=3e-4,
        gamma=0.99,
        gae_lambda=0.95,
        clip_range=0.2,
        # Small network — state space is simple (BASE_OBS_DIM features).
        policy_kwargs={"net_arch": [64, 64]},
        tensorboard_log=TB_LOG_DIR,
        verbose=1,
    )

    checkpoint_cb = CheckpointCallback(
        save_freq=CHECKPOINT_FREQ,
        save_path=CHECKPOINT_DIR,
        name_prefix="ppo_tmnf",
        verbose=1,
    )

    print(f"Starting PPO training for {TOTAL_TIMESTEPS:,} timesteps at {SPEED}× speed.")
    print(f"TensorBoard: tensorboard --logdir {TB_LOG_DIR}")
    print(f"Checkpoints: {CHECKPOINT_DIR}")

    try:
        model.learn(
            total_timesteps=TOTAL_TIMESTEPS,
            callback=checkpoint_cb,
            progress_bar=True,
        )
    finally:
        model.save(BEST_MODEL_PATH)
        print(f"Model saved to {BEST_MODEL_PATH}.zip")
        env.close()


if __name__ == "__main__":
    main()
