import math

import numpy as np
from tminterface.interface import TMInterface

from clients.base import PhaseAwareClient
from clients.phase import Phase, VELOCITY_ZERO_THRESHOLD
from constants import STEER_SCALE, UP_VECTOR
from steering import PDHeadingController, angle_diff
from track import Centerline
from utils import StateData


SPEED_MIN_KMH = 150.0
SPEED_MAX_KMH = 400.0

_controller = PDHeadingController()


class AdaptiveClient(PhaseAwareClient):
    """
    Follows the centerline using real-time state: steers toward track center, manages speed.

    Steering is computed by PDHeadingController (see steering.py for tuning guide).
    Speed is managed with a bang-bang controller: full throttle below SPEED_MAX_KMH,
    full brake above it.
    """

    def __init__(self, centerline_file: str) -> None:
        super().__init__()
        self.centerline = Centerline(centerline_file)
        self._ticks_idx = 0

    def on_registered(self, iface: TMInterface) -> None:
        print(f"Connected.")

    def on_run_step(self, iface: TMInterface, _time: int) -> None:
        state = iface.get_simulation_state()
        data = StateData(state, centerline=self.centerline)
        speed_ms = data.velocity.magnitude()
        speed_kmh = speed_ms * 3.6

        self._ticks_idx += 1
        if self._ticks_idx % 100 == 0:
            print(data)

        accelerate = False
        brake = False
        steer = 0

        match self._phase:
            case Phase.BRAKING_START:
                brake = True
                if speed_ms < VELOCITY_ZERO_THRESHOLD:
                    self._transition(Phase.RUNNING, _time)

            case Phase.RUNNING:
                # Speed control: keep below SPEED_MAX_KMH
                if speed_kmh > SPEED_MAX_KMH:
                    brake = True
                else:
                    accelerate = True

                # Steer toward centerline via PD + heading alignment
                track_fwd = self.centerline.forward_at(data.position)

                # Track right vector for projecting lateral velocity
                track_right = np.cross(track_fwd, UP_VECTOR)
                track_right_len = np.linalg.norm(track_right)
                if track_right_len > 1e-9:
                    track_right /= track_right_len

                # D term: lateral velocity component (positive = moving right)
                vel = np.array([data.velocity.x, data.velocity.y, data.velocity.z])
                lateral_vel = float(np.dot(vel, track_right))

                # Heading error: track yaw minus car yaw
                track_yaw = math.atan2(track_fwd[0], track_fwd[2])
                heading_err = angle_diff(track_yaw, data.rotation.yaw())

                lateral = data.lateral_offset or 0.0
                steer_pct = _controller.compute_steer(lateral, lateral_vel, heading_err)
                steer_pct = max(-100.0, min(100.0, steer_pct))
                steer = int(steer_pct / 100.0 * STEER_SCALE)

        iface.set_input_state(accelerate=accelerate, brake=brake, steer=steer)
