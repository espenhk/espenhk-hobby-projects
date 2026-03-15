from __future__ import annotations

from dataclasses import dataclass

import yaml

from utils import StateData


@dataclass
class RewardConfig:
    """
    All reward weights in one place — tweak here or in reward_config.yaml.

    Signs:
        Positive weights add reward (encourage the behaviour).
        Negative weights subtract reward (penalise the behaviour).
    """

    # --- Progress ---
    # Reward proportional to how far along the track the car advanced this step.
    # Large value because this is the primary objective.
    progress_weight: float = 10.0

    # --- Centerline adherence ---
    # Penalty = centerline_weight * |lateral_offset| ** centerline_exp
    # Negative weight means larger offset → more negative reward.
    # centerline_exp=2 makes the penalty grow quadratically (small drifts forgiven,
    # large drifts heavily penalised).
    centerline_weight: float = -0.5
    centerline_exp: float = 2.0

    # --- Speed ---
    # Small reward per m/s to break ties and encourage not braking unnecessarily.
    speed_weight: float = 0.01

    # --- Time cost ---
    # Tiny negative reward every tick so the agent prefers finishing fast.
    step_penalty: float = -0.01

    # --- Finish rewards ---
    # One-time bonus when track_progress reaches 1.0.
    finish_bonus: float = 100.0
    # Additional bonus/penalty relative to a par time.
    # Negative weight means slower = more negative (finishing 10 s over par loses 1.0).
    finish_time_weight: float = -0.1
    par_time_s: float = 60.0

    # --- Acceleration bonus ---
    # Small flat reward every step the throttle is pressed.
    # Prevents the policy from preferring coast actions when they produce similar progress.
    accel_bonus: float = 0.10

    # --- Airborne penalty ---
    # Applied when the car has ≤1 wheel in contact AND vertical_offset ≤ 0.
    # vertical_offset > 0 means the car is above the centerline — that's a jump, no penalty.
    # vertical_offset ≤ 0 with few wheel contacts means the car has fallen off or gone sideways.
    airborne_penalty: float = -1.0

    # --- Episode termination threshold ---
    # The env ends the episode when |lateral_offset| exceeds this (in metres).
    crash_threshold_m: float = 10.0

    @classmethod
    def from_yaml(cls, path: str) -> RewardConfig:
        with open(path) as f:
            data = yaml.safe_load(f) or {}
        return cls(**data)


class RewardCalculator:
    """Stateless reward computation — call compute() every RL step."""

    def __init__(self, config: RewardConfig):
        self.config = config

    def compute(
        self,
        prev: StateData,
        curr: StateData,
        finished: bool,
        elapsed_s: float,
        accelerating: bool = False,
    ) -> float:
        cfg = self.config
        reward = 0.0

        # Progress: reward for advancing along the track this step.
        if curr.track_progress is not None and prev.track_progress is not None:
            delta = curr.track_progress - prev.track_progress
            reward += delta * cfg.progress_weight

        # Centerline: quadratic penalty for lateral deviation.
        if curr.lateral_offset is not None:
            reward += cfg.centerline_weight * abs(curr.lateral_offset) ** cfg.centerline_exp

        # Speed: small reward for going fast.
        reward += cfg.speed_weight * curr.velocity.magnitude()

        # Acceleration bonus: nudge the policy away from coasting.
        if accelerating:
            reward += cfg.accel_bonus

        # Time cost: constant small penalty per tick.
        reward += cfg.step_penalty

        # Finish: one-time bonus + time-relative bonus.
        if finished:
            reward += cfg.finish_bonus
            over_par = elapsed_s - cfg.par_time_s
            reward += cfg.finish_time_weight * over_par  # negative if slow

        # Airborne penalty: only when below or beside the centerline.
        if curr.vertical_offset is not None:
            wheels_in_contact = sum(w.contact for w in curr.wheels)
            airborne = wheels_in_contact <= 1
            # vertical_offset > 0 → car is above centerline → legitimate jump → no penalty
            if airborne and curr.vertical_offset <= 0.0:
                reward += cfg.airborne_penalty

        return reward
