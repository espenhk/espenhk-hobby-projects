"""
Driving policies for TMNF.

SimplePolicy       — hand-tuned PD controller (reference baseline)
WeightedLinearPolicy — trainable linear policy; weights stored in YAML
"""

from __future__ import annotations

import os

import numpy as np
import yaml


# ---------------------------------------------------------------------------
# SimplePolicy
# ---------------------------------------------------------------------------

class SimplePolicy:
    """
    Hardcoded PD+heading policy mirroring AdaptiveClient's steering formula.

    Maps obs[1] (lateral offset) and obs[3] (yaw error) to three discrete
    steering actions (accel+left / accel+straight / accel+right).

    The D term approximates lateral velocity as Δlateral_offset per tick.
    """

    LATERAL_GAIN    = 16.0   # P: steer% per metre off-centre
    DERIVATIVE_GAIN =  8.0   # D: steer% per m/tick of lateral drift
    HEADING_GAIN    =  5.0   # steer% per radian of heading error
    STEER_THRESHOLD =  2.0   # deadzone before committing to left/right

    def __init__(self):
        self._prev_lateral = 0.0

    def __call__(self, obs) -> int:
        lateral = obs[1]
        yaw     = obs[3]

        lateral_vel        = lateral - self._prev_lateral
        self._prev_lateral = lateral

        steer_pct = (
            -lateral     * self.LATERAL_GAIN
            - lateral_vel  * self.DERIVATIVE_GAIN
            + yaw          * self.HEADING_GAIN
        )

        if steer_pct < -self.STEER_THRESHOLD:
            return 6   # accel + left
        elif steer_pct > self.STEER_THRESHOLD:
            return 8   # accel + right
        else:
            return 7   # accel + straight


# ---------------------------------------------------------------------------
# WeightedLinearPolicy
# ---------------------------------------------------------------------------

class WeightedLinearPolicy:
    """
    Linear policy: steer and throttle decisions from independent dot products.

        steer_score    = dot(steer_weights,    obs)
        throttle_score = dot(throttle_weights, obs)

    Steer score:
        < -steer_threshold    → left   (action +0)
        within threshold      → straight (action +1)
        > +steer_threshold    → right  (action +2)

    Throttle score:
        < -throttle_threshold → brake  (action 0–2)
        within threshold      → coast  (action 3–5)
        > +throttle_threshold → accel  (action 6–8)

    action = throttle_idx * 3 + steer_idx

    Weights are loaded from / saved to a YAML file for observability.
    Create via WeightedLinearPolicy(file) or WeightedLinearPolicy.from_cfg(dict).
    """

    OBS_NAMES = [
        "speed_ms",
        "lateral_offset_m",
        "vertical_offset_m",
        "yaw_error_rad",
        "pitch_rad",
        "roll_rad",
        "track_progress",
        "turning_rate",
        "wheel_0_contact",
        "wheel_1_contact",
        "wheel_2_contact",
        "wheel_3_contact",
        "angular_vel_x",
        "angular_vel_y",
        "angular_vel_z",
    ]

    # Typical magnitude of each obs feature. obs is divided by these before the
    # dot product so every weight operates on a ~[-1, 1] input, making mutation
    # steps comparable across features regardless of raw unit scale.
    OBS_SCALES = np.array([
        50.0,    # speed_ms         — typical ~50 m/s at race pace
        5.0,     # lateral_offset_m — crash threshold 25 m, normal range ±2–3 m
        2.0,     # vertical_offset_m
        3.14159, # yaw_error_rad    — full range is [-π, π]
        0.3,     # pitch_rad
        0.3,     # roll_rad
        1.0,     # track_progress   — already [0, 1]
        65536.0, # turning_rate     — raw TMInterface steer value, ±65536
        1.0,     # wheel_0_contact  — already {0, 1}
        1.0,     # wheel_1_contact
        1.0,     # wheel_2_contact
        1.0,     # wheel_3_contact
        5.0,     # angular_vel_x    — rad/s, typical peak ±5
        5.0,     # angular_vel_y
        5.0,     # angular_vel_z
    ], dtype=np.float32)

    @classmethod
    def get_obs_names(cls, n_lidar_rays: int = 0) -> list[str]:
        """Return the full observation name list for *n_lidar_rays* LIDAR rays."""
        return cls.OBS_NAMES + [f"lidar_{i}" for i in range(n_lidar_rays)]

    @classmethod
    def get_obs_scales(cls, n_lidar_rays: int = 0) -> np.ndarray:
        """Return the full scale vector. LIDAR values are already ~[0,1] so scale=1."""
        return np.concatenate([cls.OBS_SCALES, np.ones(n_lidar_rays, dtype=np.float32)])

    def __init__(self, weights_file: str, n_lidar_rays: int = 0):
        self._weights_file = weights_file
        self._n_lidar_rays = n_lidar_rays
        cfg = self._load_or_init()
        self._apply_cfg(cfg)
        print(f"[WeightedLinearPolicy] loaded weights from {weights_file}")

    @classmethod
    def from_cfg(cls, cfg: dict, n_lidar_rays: int = 0) -> "WeightedLinearPolicy":
        """Create a policy from a weights dict (not backed by a file)."""
        obj = object.__new__(cls)
        obj._weights_file = None
        obj._n_lidar_rays = n_lidar_rays
        obj._apply_cfg(cfg)
        return obj

    # ------------------------------------------------------------------
    # Weights dict I/O
    # ------------------------------------------------------------------

    def to_cfg(self) -> dict:
        names = self.get_obs_names(self._n_lidar_rays)
        return {
            "steer_threshold":    float(self._steer_t),
            "throttle_threshold": float(self._throttle_t),
            "steer_weights":    {n: float(self._steer_w[i])    for i, n in enumerate(names)},
            "throttle_weights": {n: float(self._throttle_w[i]) for i, n in enumerate(names)},
        }

    def save(self, path: str) -> None:
        with open(path, "w") as f:
            yaml.dump(self.to_cfg(), f, default_flow_style=False, sort_keys=False)

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------

    def mutated(self, scale: float = 0.1) -> "WeightedLinearPolicy":
        """Return a new policy with small Gaussian perturbation applied to all weights."""
        rng = np.random.default_rng()
        cfg = self.to_cfg()
        for group in ("steer_weights", "throttle_weights"):
            for k in cfg[group]:
                cfg[group][k] += float(rng.normal(-scale, scale))
        return WeightedLinearPolicy.from_cfg(cfg, n_lidar_rays=self._n_lidar_rays)

    # ------------------------------------------------------------------
    # Callable interface
    # ------------------------------------------------------------------

    def __call__(self, obs) -> int:
        norm_obs       = obs / self.get_obs_scales(self._n_lidar_rays)
        steer_score    = float(np.dot(self._steer_w,    norm_obs))
        throttle_score = float(np.dot(self._throttle_w, norm_obs))

        if steer_score < -self._steer_t:
            steer_idx = 0
        elif steer_score > self._steer_t:
            steer_idx = 2
        else:
            steer_idx = 1

        if throttle_score < -self._throttle_t:
            throttle_idx = 0
        elif throttle_score > self._throttle_t:
            throttle_idx = 2
        else:
            throttle_idx = 1

        return throttle_idx * 3 + steer_idx

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _apply_cfg(self, cfg: dict) -> None:
        names = self.get_obs_names(self._n_lidar_rays)
        self._steer_w    = np.array([cfg["steer_weights"][n]    for n in names], dtype=np.float32)
        self._throttle_w = np.array([cfg["throttle_weights"][n] for n in names], dtype=np.float32)
        self._steer_t    = float(cfg["steer_threshold"])
        self._throttle_t = float(cfg["throttle_threshold"])

    def _load_or_init(self) -> dict:
        names = self.get_obs_names(self._n_lidar_rays)
        if os.path.exists(self._weights_file):
            with open(self._weights_file) as f:
                cfg = yaml.safe_load(f)
            # Migrate: fill in any missing LIDAR keys with 0.0 (neutral starting point)
            migrated = False
            for group in ("steer_weights", "throttle_weights"):
                for n in names:
                    if n not in cfg[group]:
                        cfg[group][n] = 0.0
                        migrated = True
            if migrated:
                with open(self._weights_file, "w") as f:
                    yaml.dump(cfg, f, default_flow_style=False, sort_keys=False)
                print(f"[WeightedLinearPolicy] migrated weights file with new LIDAR keys → {self._weights_file}")
            return cfg

        rng = np.random.default_rng()
        cfg = {
            "steer_threshold":    0.5,
            "throttle_threshold": 0.5,
            "steer_weights":    {n: float(rng.standard_normal()) for n in names},
            "throttle_weights": {n: float(rng.standard_normal()) for n in names},
        }
        with open(self._weights_file, "w") as f:
            yaml.dump(cfg, f, default_flow_style=False, sort_keys=False)
        print(f"[WeightedLinearPolicy] initialised random weights → {self._weights_file}")
        return cfg
