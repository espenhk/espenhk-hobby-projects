import math

from tminterface.client import Client
from tminterface.interface import TMInterface

from clients.phase import Phase, VELOCITY_ZERO_THRESHOLD
from track import Centerline
from utils import StateData, get_position


SPEED_MIN_KMH = 20.0
SPEED_MAX_KMH = 40.0


class AdaptiveClient(Client):
    """Follows the centerline using real-time state: steers toward track center, manages speed."""

    LATERAL_GAIN = 10.0   # steer % per metre off-center
    HEADING_GAIN = 40.0  # steer % per radian of heading error

    def __init__(self, centerline_file: str, speed: float = 1.0):
        super().__init__()
        self.speed = speed
        self.centerline = Centerline(centerline_file)
        self._phase = Phase.BRAKING_START
        self._phase_start_ms = 0
        self._ticks_idx = 0

    def on_registered(self, iface: TMInterface):
        print(f"Connected. AdaptiveClient running at {self.speed}x speed.")
        iface.execute_command(f"set speed {self.speed}")

    def on_run_step(self, iface: TMInterface, _time: int):
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
                # Speed control: keep between SPEED_MIN_KMH and SPEED_MAX_KMH
                if speed_kmh > SPEED_MAX_KMH:
                    brake = True
                else:
                    accelerate = True  # always accelerate unless braking

                # Steer toward centerline using lateral offset + heading error
                pos = get_position(state)
                track_fwd = self.centerline.forward_at(pos)
                track_yaw = math.atan2(track_fwd[0], track_fwd[2])
                car_yaw = data.rotation.yaw()
                heading_err = _angle_diff(track_yaw, car_yaw)

                lateral = data.lateral_offset or 0.0
                steer_pct = (
                    -lateral * self.LATERAL_GAIN
                    + heading_err * self.HEADING_GAIN
                )
                steer_pct = max(-100.0, min(100.0, steer_pct))
                steer = int(steer_pct / 100.0 * 65536)

        iface.set_input_state(accelerate=accelerate, brake=brake, steer=steer)

    def _transition(self, phase: Phase, current_time_ms: int):
        print(f"Phase: {self._phase.name} -> {phase.name}")
        self._phase = phase
        self._phase_start_ms = current_time_ms


def _angle_diff(target: float, current: float) -> float:
    """Signed angular difference target - current, wrapped to [-pi, pi]."""
    diff = (target - current + math.pi) % (2 * math.pi) - math.pi
    return diff
