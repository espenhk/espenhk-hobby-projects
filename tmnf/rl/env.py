"""
TMNFEnv — Gymnasium environment wrapping TMInterface for RL training.

Observation space (15 + n_lidar_rays floats, dtype float32)
------------------------------------------------------------
  [0]  speed_ms          — vehicle speed in m/s
  [1]  lateral_offset_m  — metres from centreline (neg=left, pos=right)
  [2]  vertical_offset_m — metres above (+) / below (-) centreline
  [3]  yaw_error_rad     — signed heading error vs track direction, [-π, π]
  [4]  pitch_rad         — nose-up/down rotation
  [5]  roll_rad          — tilt left/right
  [6]  track_progress    — fraction of track completed, [0, 1]
  [7]  turning_rate      — current steering angle reported by the game
  [8]  wheel_0_contact   — 1.0 if front-left wheel has ground contact, else 0.0
  [9]  wheel_1_contact   — front-right
  [10] wheel_2_contact   — rear-left
  [11] wheel_3_contact   — rear-right
  [12] angular_vel_x     — roll rate  (rad/s)
  [13] angular_vel_y     — yaw rate   (rad/s)
  [14] angular_vel_z     — pitch rate (rad/s)
  [15+] lidar_i          — LIDAR wall distances, ~[0, 1], left-to-right across
                           the car's forward view (only present if n_lidar_rays > 0)

Action space
------------
  Discrete(9) — see clients/rl_client.py ACTIONS table.
  0-2: brake  + left/straight/right
  3-5: coast  + left/straight/right
  6-8: accel  + left/straight/right

Episode lifecycle
-----------------
  reset() → respawn car → brake to stop → return initial obs
  step()  → set action, wait for next game tick, compute reward
  Terminated when: track_progress ≥ 1.0  (finished)
               or: |lateral_offset| > crash_threshold_m  (crashed)
  Truncated  when: elapsed_time > max_episode_time_s

Notes on threading
------------------
  TMInterface calls on_run_step() on its own thread.
  The RL training loop runs on the calling thread.
  A daemon keepalive thread keeps iface.running alive.
  See clients/rl_client.py for the synchronisation details.
"""

from __future__ import annotations

import os
import time
import threading
from typing import Any

import numpy as np
import gymnasium as gym
from gymnasium import spaces
from tminterface.interface import TMInterface

from clients.rl_client import ACTIONS, RLClient, StepState, N_ACTIONS
from rl.reward import RewardConfig, RewardCalculator
from lidar import LidarSensor


_BASE_OBS_DIM = 15
_DEFAULT_REWARD_CONFIG = os.path.join(os.path.dirname(__file__), "..", "config", "reward_config.yaml")


class TMNFEnv(gym.Env):
    """
    Gymnasium environment for TMNF reinforcement learning.

    Parameters
    ----------
    centerline_file:
        Path to the .npy centreline file (relative to tmnf/ working dir).
    speed:
        Game speed multiplier passed to TMInterface (e.g. 10.0 = 10× speed).
    reward_config:
        RewardConfig instance.  If None, loaded from config/reward_config.yaml.
    max_episode_time_s:
        Wall-clock seconds (at 1× game speed) before the episode is truncated.
    """

    metadata = {"render_modes": []}

    def __init__(
        self,
        centerline_file: str,
        speed: float = 10.0,
        reward_config: RewardConfig | None = None,
        max_episode_time_s: float = 120.0,
        n_lidar_rays: int = 0,
        auto_respawn_on_finish: bool = True,
    ) -> None:
        super().__init__()

        self._reward_config = reward_config or RewardConfig.from_yaml(_DEFAULT_REWARD_CONFIG)
        self._reward_calc = RewardCalculator(self._reward_config)
        self._max_episode_time_s = max_episode_time_s
        self._auto_respawn_on_finish = auto_respawn_on_finish

        # Optional LIDAR sensor (screenshot-based wall distances)
        if n_lidar_rays > 0:
            self._lidar: LidarSensor | None = LidarSensor(n_lidar_rays)
        else:
            self._lidar = None

        obs_dim = _BASE_OBS_DIM + n_lidar_rays
        # Observation: unbounded (SB3's VecNormalize can normalise online)
        self.observation_space = spaces.Box(
            low=-np.inf,
            high=np.inf,
            shape=(obs_dim,),
            dtype=np.float32,
        )
        self.action_space = spaces.Discrete(N_ACTIONS)

        # Set up TMInterface
        self._client = RLClient(centerline_file, speed=speed,
                                auto_respawn_on_finish=auto_respawn_on_finish)
        self._iface = TMInterface()

        # The keepalive thread owns register() so the message-pump is already
        # running when the game sends S_ON_REGISTERED.  Calling register() on the
        # main thread first and then starting the pump is the race condition that
        # causes the 2000 ms timeout.
        self._keepalive = threading.Thread(target=self._run_iface_loop, daemon=True)
        self._keepalive.start()

        print("Waiting for TMInterface connection...")
        if not self._client.wait_registered(timeout=15.0):
            raise RuntimeError(
                "TMInterface did not connect within 15 s — is the game running?"
            )
        print("Connected.")

        # Episode tracking
        self._prev_state = None
        self._elapsed_s: float = 0.0
        self._episode_start_s: float = 0.0
        self._laps_completed: int = 0

        # Skip-event telemetry — reset each episode, printed at episode end.
        self._ep_rl_steps: int = 0         # env.step() calls this episode
        self._ep_total_ticks: int = 0      # game ticks covered (≥ rl_steps)
        self._ep_max_skip: int = 0         # worst single-step skip
        self._total_rl_steps: int = 0      # lifetime step counter (for periodic log)

    # ------------------------------------------------------------------
    # Gymnasium interface
    # ------------------------------------------------------------------

    def reset(
        self,
        *,
        seed: int | None = None,
        options: dict[str, Any] | None = None,
    ) -> tuple[np.ndarray, dict]:
        super().reset(seed=seed)

        self._client.request_respawn()
        init_step = self._client.wait_episode_ready()

        self._prev_state = init_step.state_data
        self._elapsed_s = 0.0
        self._episode_start_s = time.monotonic()
        self._laps_completed = 0
        self._ep_rl_steps = 0
        self._ep_total_ticks = 0
        self._ep_max_skip = 0

        obs = self._make_obs(init_step)
        return obs, {}

    def step(self, action: int) -> tuple[np.ndarray, float, bool, bool, dict]:
        self._client.set_action(int(action))
        step = self._client.get_step_state()

        data = step.state_data
        finished = step.finished or (data.track_progress is not None and data.track_progress >= 1.0)
        crashed  = (data.lateral_offset is not None
                    and abs(data.lateral_offset) > self._reward_config.crash_threshold_m)
        self._elapsed_s = time.monotonic() - self._episode_start_s

        # --- skip-event telemetry ---
        n = step.ticks_this_step
        self._ep_rl_steps += 1
        self._ep_total_ticks += n
        self._total_rl_steps += 1
        if n > self._ep_max_skip:
            self._ep_max_skip = n

        accelerating = ACTIONS[action][0]  # first element is the accelerate bool
        lidar_rays = self._lidar.get_distances() if self._lidar is not None else None

        reward = self._reward_calc.compute(
            prev=self._prev_state,
            curr=data,
            finished=finished,
            elapsed_s=self._elapsed_s,
            accelerating=accelerating,
            lidar_rays=lidar_rays,
            n_ticks=step.ticks_this_step,
        )

        time_over = self._elapsed_s > self._max_episode_time_s

        # Auto-respawn on finish: the game thread has already queued a respawn;
        # wait for the car to stop at the new spawn, then continue the episode.
        if finished and self._auto_respawn_on_finish and not time_over:
            self._laps_completed += 1
            init_step = self._client.wait_episode_ready()
            self._prev_state = init_step.state_data
            obs = self._make_obs(init_step)
            info = {
                "track_progress": 0.0,
                "lateral_offset": 0.0,
                "finished": True,
                "laps_completed": self._laps_completed,
                "elapsed_s": self._elapsed_s,
                "pos_x": init_step.state_data.position.x,
                "pos_z": init_step.state_data.position.z,
            }
            return obs, reward, False, False, info

        terminated = finished or crashed
        # step.done signals a hard crash (>50 m off, handled by client safety net)
        truncated = (step.done and not terminated) or time_over

        if terminated or truncated:
            self._log_skip_stats()

        self._prev_state = data
        obs = self._make_obs(step)
        info = {
            "track_progress": data.track_progress or 0.0,
            "lateral_offset": data.lateral_offset or 0.0,
            "finished": finished,
            "laps_completed": self._laps_completed,
            "elapsed_s": self._elapsed_s,
            "pos_x": data.position.x,
            "pos_z": data.position.z,
            # Skip stats also surfaced in info so callers can aggregate them.
            "ticks_this_step": n,
            "ep_rl_steps": self._ep_rl_steps,
            "ep_total_ticks": self._ep_total_ticks,
            "ep_skipped_ticks": self._ep_total_ticks - self._ep_rl_steps,
            "ep_max_skip": self._ep_max_skip,
        }

        return obs, reward, terminated, truncated, info

    def close(self) -> None:
        self._client.stop()
        self._iface.close()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _log_skip_stats(self) -> None:
        """Print a per-episode skip-event summary.

        Skipped ticks = game ticks that fired while the RL thread was still
        processing the previous step. A high skip rate means the policy + reward
        computation is too slow to keep up with the game at the current speed
        multiplier.

        Example output (healthy, ~1 skip per step at 10x):
            [skip] ep 42 | rl_steps=87  game_ticks=102  skipped=15  avg=1.17  max=3
        Example output (falling behind badly):
            [skip] ep 42 | rl_steps=87  game_ticks=340  skipped=253  avg=3.91  max=18
        """
        skipped = self._ep_total_ticks - self._ep_rl_steps
        avg = self._ep_total_ticks / self._ep_rl_steps if self._ep_rl_steps else 0.0
        print(
            f"[skip] ep_step {self._total_rl_steps} | "
            f"rl_steps={self._ep_rl_steps}  "
            f"game_ticks={self._ep_total_ticks}  "
            f"skipped={skipped}  "
            f"avg={avg:.2f}  "
            f"max={self._ep_max_skip}"
        )

    def _make_obs(self, step: StepState) -> np.ndarray:
        d = step.state_data
        state = np.array(
            [
                d.velocity.magnitude(),                    # [0] speed m/s
                d.lateral_offset or 0.0,                   # [1] lateral offset m
                d.vertical_offset or 0.0,                  # [2] vertical offset m
                step.yaw_error,                            # [3] heading error rad
                d.rotation.pitch(),                        # [4] pitch rad
                d.rotation.roll(),                         # [5] roll rad
                d.track_progress or 0.0,                   # [6] progress 0-1
                d.turning_rate,                            # [7] turning rate
                float(d.wheels[0].contact),                # [8-11] wheel contacts
                float(d.wheels[1].contact),
                float(d.wheels[2].contact),
                float(d.wheels[3].contact),
                d.angular_velocity.x,                      # [12-14] angular vel
                d.angular_velocity.y,
                d.angular_velocity.z,
            ],
            dtype=np.float32,
        )
        if self._lidar is not None:
            state = np.concatenate([state, self._lidar.get_distances()])
        return state

    def _run_iface_loop(self) -> None:
        """Keepalive thread: owns register() so the message pump is live before
        the game sends S_ON_REGISTERED, eliminating the 2000 ms timeout race."""
        self._iface.register(self._client)
        while self._iface.running:
            time.sleep(0.001)  # yield CPU; sleep(0) spun too tightly and competed with game/RL threads
