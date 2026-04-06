import logging
import math

import numpy as np

logger = logging.getLogger(__name__)
from tminterface.client import Client
from tminterface.interface import TMInterface

from clients.phase import Phase, VELOCITY_ZERO_THRESHOLD
from track import Centerline
from utils import StateData, get_position


SPEED_MIN_KMH = 150.0
SPEED_MAX_KMH = 400.0

_UP = np.array([0.0, 1.0, 0.0])


class AdaptiveClient(Client):
    """
    Follows the centerline using real-time state: steers toward track center, manages speed.

    Steering is the sum of three terms:

    P — position error (LATERAL_GAIN)
        Pulls the car back to center proportional to how far off it is.
        No memory, no foresight — only knows where the car is right now.

    D — lateral velocity (DERIVATIVE_GAIN)
        Opposes sideways motion. When the car is already correcting and moving
        back toward center, D produces a counter-steer to prevent overshoot.
        It doesn't care about position, only rate of drift.

    Heading (HEADING_GAIN)
        Aligns the car's nose with the track's forward direction. Ignores
        position entirely — a car on the centerline but pointing diagonally
        still gets a correction. Makes the car anticipate curves rather than
        reacting to drift after the fact.

    Tuning guide — symptom -> cause:
        Car corrects slowly on straights                    -> P too low
        Smooth sine-wave oscillation, consistent amplitude  -> P too high
        Oscillation with growing amplitude                  -> D too low
        Car sluggishly drifts, resists its own correction   -> D too high
        Cuts corners / overshoots turns                     -> Heading too low
        Constant twitching even when centered and aligned   -> Heading too high
        Snaking on straights while centered                 -> Heading too high

    Diagnostic tip: watch the car when it is already on the centerline.
        Still oscillating -> P and D are fighting, not heading.
        Drifting wide in turns -> heading.
        Correcting but overshooting every time -> D too low relative to P.
    """

    LATERAL_GAIN    = 16.0   # steer % per metre off-center (P term)
    DERIVATIVE_GAIN = 8.0   # steer % per m/s of lateral velocity (D term — damping)
    HEADING_GAIN    = 5.0   # steer % per radian of heading error

    def __init__(self, centerline_file: str) -> None:
        super().__init__()
        self.centerline = Centerline(centerline_file)
        self._phase = Phase.BRAKING_START
        self._phase_start_ms = 0
        self._ticks_idx = 0

    def on_registered(self, iface: TMInterface) -> None:
        logger.info("Connected.")

    def on_run_step(self, iface: TMInterface, _time: int) -> None:
        state = iface.get_simulation_state()
        data = StateData(state, centerline=self.centerline)
        speed_ms = data.velocity.magnitude()
        speed_kmh = speed_ms * 3.6

        self._ticks_idx += 1
        if self._ticks_idx % 100 == 0:
            logger.debug("%s", data)

        accelerate = False
        brake = False
        steer = 0

        match self._phase:
            case Phase.BRAKING_START:
                brake = True
                if speed_ms < VELOCITY_ZERO_THRESHOLD:
                    self._transition(Phase.RUNNING, _time)

            case Phase.RUNNING:
                # Speed control: keep between SPEED_MIN_KMH and SPEED_MAX_KMH
                if speed_kmh > SPEED_MAX_KMH:
                    brake = True
                else:
                    accelerate = True  # always accelerate unless braking

                # Steer toward centerline: PD on lateral position + heading alignment
                pos = get_position(state)
                track_fwd = self.centerline.forward_at(pos)

                # Track right vector for projecting lateral velocity
                track_right = np.cross(track_fwd, _UP)
                track_right_len = np.linalg.norm(track_right)
                if track_right_len > 1e-9:
                    track_right /= track_right_len

                # D term: lateral velocity (positive = moving right)
                vel = np.array([data.velocity.x, data.velocity.y, data.velocity.z])
                lateral_vel = float(np.dot(vel, track_right))

                # Heading alignment: steer to match track forward direction
                track_yaw = math.atan2(track_fwd[0], track_fwd[2])
                car_yaw = data.rotation.yaw()
                heading_err = _angle_diff(track_yaw, car_yaw)

                lateral = data.lateral_offset or 0.0
                steer_pct = (
                    -lateral * self.LATERAL_GAIN        # P: correct position error
                    - lateral_vel * self.DERIVATIVE_GAIN  # D: damp lateral motion
                    + heading_err * self.HEADING_GAIN   # align to track direction
                )
                steer_pct = max(-100.0, min(100.0, steer_pct))
                steer = int(steer_pct / 100.0 * 65536)

        iface.set_input_state(accelerate=accelerate, brake=brake, steer=steer)

    def _transition(self, phase: Phase, current_time_ms: int) -> None:
        logger.debug("Phase: %s -> %s", self._phase.name, phase.name)
        self._phase = phase
        self._phase_start_ms = current_time_ms


def _angle_diff(target: float, current: float) -> float:
    """Signed angular difference target - current, wrapped to [-pi, pi]."""
    diff = (target - current + math.pi) % (2 * math.pi) - math.pi
    return diff
