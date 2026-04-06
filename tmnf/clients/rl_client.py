"""
RLClient — TMInterface client designed for reinforcement learning.

Threading model
---------------
TMInterface fires on_run_step() on its own internal thread.
The RL training loop runs on the main (or another) thread.
They communicate through:

  action_idx   : the RL thread writes, the game thread reads (lock-protected)
  _state_queue : the game thread writes one StepState per tick;
                 the RL thread blocks on get() to receive it.
  _respawn_event    : RL thread sets → game thread calls iface.respawn()
  _episode_ready    : game thread sets → RL thread unblocks from reset()

Because the game runs at high speed (e.g. 10×) and the policy evaluation
takes some time, multiple game ticks may pass before the RL thread reads a
state. _state_queue has maxsize=1 with a drain-before-put strategy so the
RL thread always gets the *latest* state (no stale backlog).
"""

from __future__ import annotations

import math
import queue
import threading
from dataclasses import dataclass
from typing import Any

import numpy as np
from tminterface.client import Client
from tminterface.interface import TMInterface

from clients.phase import Phase, VELOCITY_ZERO_THRESHOLD
from track import Centerline
from utils import StateData, get_position

import logging
logger = logging.getLogger(__name__)

_UP = np.array([0.0, 1.0, 0.0])

# Hard-limit lateral offset before the client itself declares the episode done.
# This is a safety net — the env's crash_threshold_m (default 10 m) triggers first.
_HARD_CRASH_THRESHOLD_M = 50.0


# ---------------------------------------------------------------------------
# Discrete action table
# Index → (accelerate, brake, steer_percent)
# steer_percent is in [-100, 100]; converted to [-65536, 65536] when applied.
# ---------------------------------------------------------------------------
ACTIONS: list[tuple[bool, bool, int, str]] = [
    (False, True,   -100, "brake LEFT"),  # 0: brake  + full left
    (False, True,      0, "brake"),       # 1: brake  + straight
    (False, True,    100, "brake RIGHT"), # 2: brake  + full right
    (False, False, -100, "coast LEFT"),   # 3: coast  + full left
    (False, False,    0, "coast"),        # 4: coast  + straight
    (False, False,  100, "coast RIGHT"),  # 5: coast  + full right
    (True,  False, -100, "accelerate LEFT"),   # 6: accel  + full left
    (True,  False,    0, "accelerate"),        # 7: accel  + straight   ← default
    (True,  False,  100, "accelerate right")   # 8: accel  + full right
]
N_ACTIONS = len(ACTIONS)

def get_action_description(idx: int) -> str:
    return ACTIONS[idx][3]

@dataclass
class StepState:
    """Everything the env needs to compute observations and rewards."""
    state_data: StateData
    yaw_error: float   # signed radians: track heading minus car heading, in [-π, π]
    done: bool         # True if game client detected a hard termination condition
    finished: bool = False  # True when car crossed the finish line


class RLClient(Client):
    """TMInterface client used by TMNFEnv during RL training."""

    def __init__(self, centerline_file: str, speed: float = 10.0,
                 auto_respawn_on_finish: bool = False) -> None:
        super().__init__()
        self.speed = speed
        self.centerline = Centerline(centerline_file)
        self._auto_respawn_on_finish = auto_respawn_on_finish

        # Shared state — written by RL thread, read by game thread
        self._action_idx: int = 7   # default: accel + straight
        self._action_lock = threading.Lock()

        # Shared state — written by game thread, read by RL thread
        self._state_queue: queue.Queue[StepState] = queue.Queue(maxsize=1)
        self._respawn_event = threading.Event()
        self._episode_ready = threading.Event()

        self._phase = Phase.BRAKING_START
        self._registered_event = threading.Event()
        self._stop_event = threading.Event()

        # Set by game thread when a lap completes (auto-respawn path only).
        # The game thread acts on it the following tick, so the finish step
        # is delivered to the RL thread before the respawn is triggered.
        self._finish_respawn_pending: bool = False
        self._last_step_state: StepState | None = None

    # ------------------------------------------------------------------
    # RL-thread API
    # ------------------------------------------------------------------

    def wait_registered(self, timeout: float = 15.0) -> bool:
        """Block until on_registered fires (or timeout). Returns True on success."""
        return self._registered_event.wait(timeout=timeout)

    def stop(self) -> None:
        """Unblock any waiting RL-thread calls so the process can exit cleanly."""
        self._stop_event.set()
        self._episode_ready.set()   # unblock wait_episode_ready

    def set_action(self, action_idx: int) -> None:
        """Set the next action. Thread-safe."""
        with self._action_lock:
            self._action_idx = action_idx

    def get_step_state(self) -> StepState:
        """Block until the game thread delivers the next state."""
        while not self._stop_event.is_set():
            try:
                return self._state_queue.get(timeout=1.0)
            except queue.Empty:
                continue
        raise RuntimeError("RLClient stopped while waiting for step state")

    def request_respawn(self) -> None:
        """Signal the game thread to respawn the car. Call before wait_episode_ready()."""
        self._episode_ready.clear()
        self._respawn_event.set()

    def wait_episode_ready(self) -> StepState:
        """
        Block until the car has stopped after respawn (BRAKING_START → RUNNING).
        Returns the first state of the new episode.
        """
        while not self._stop_event.is_set():
            if self._episode_ready.wait(timeout=1.0):
                break
        if self._stop_event.is_set():
            raise RuntimeError("RLClient stopped while waiting for episode ready")
        self._episode_ready.clear()
        return self._state_queue.get(timeout=5.0)

    # ------------------------------------------------------------------
    # TMInterface callbacks — called by the game thread
    # ------------------------------------------------------------------

    def on_registered(self, iface: TMInterface) -> None:
        logger.info("Connected. RLClient running at %sx speed.", self.speed)
        iface.execute_command(f"set speed {self.speed}")
        self._registered_event.set()

    def on_simulation_begin(self, iface: TMInterface) -> None:
        """Fires when TMInterface starts replay validation after the car finishes.
        If we were in RUNNING phase, treat it as a finish event and deliver a
        synthetic finish step so the RL thread is not left waiting indefinitely."""
        if self._phase != Phase.RUNNING:
            return  # Our own give_up() respawn — ignore
        if self._last_step_state is None:
            return  # No cached state to synthesize from
        synthetic = StepState(
            state_data=self._last_step_state.state_data,
            yaw_error=self._last_step_state.yaw_error,
            done=False,
            finished=True,
        )
        self._drain_and_put(synthetic)
        if self._auto_respawn_on_finish:
            # Mark pending so the first on_run_step of the replay calls give_up().
            self._finish_respawn_pending = True
        # Non-auto-respawn: RL thread sees finished=True → terminated=True →
        # calls reset() → request_respawn() → _respawn_event → on_run_step give_up()

    def on_run_step(self, iface: TMInterface, _time: int) -> None:
        # Handle a pending respawn request from the RL thread.
        if self._respawn_event.is_set():
            self._respawn_event.clear()
            iface.give_up()
            self._phase = Phase.BRAKING_START
            return

        state = iface.get_simulation_state()
        data = StateData(state, centerline=self.centerline)
        speed_ms = data.velocity.magnitude()

        match self._phase:
            case Phase.BRAKING_START:
                iface.set_input_state(brake=True)
                if speed_ms < VELOCITY_ZERO_THRESHOLD:
                    self._phase = Phase.RUNNING
                    step_state = StepState(
                        state_data=data,
                        yaw_error=self._compute_yaw_error(state, data),
                        done=False,
                    )
                    self._drain_and_put(step_state)
                    self._episode_ready.set()

            case Phase.RUNNING:
                # Pending auto-respawn from the previous tick's lap completion:
                # act on it here so the finish step was already delivered first.
                if self._finish_respawn_pending:
                    self._finish_respawn_pending = False
                    self._episode_ready.clear()
                    iface.give_up()   # restart race from position zero
                    self._phase = Phase.BRAKING_START
                    return

                with self._action_lock:
                    action_idx = self._action_idx
                accelerate, brake, steer_pct, _ = ACTIONS[action_idx]
                iface.set_input_state(
                    accelerate=accelerate,
                    brake=brake,
                    steer=int(steer_pct / 100 * 65536),
                )

                finished  = data.track_progress is not None and data.track_progress >= 1.0
                hard_crash = (data.lateral_offset is not None
                              and abs(data.lateral_offset) > _HARD_CRASH_THRESHOLD_M)

                if finished and self._auto_respawn_on_finish:
                    # Deliver the finish step with done=False; respawn next tick.
                    self._finish_respawn_pending = True
                    done = False
                else:
                    done = finished or hard_crash

                step_state = StepState(
                    state_data=data,
                    yaw_error=self._compute_yaw_error(state, data),
                    done=done,
                    finished=finished,
                )
                self._drain_and_put(step_state)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _drain_and_put(self, step_state: StepState) -> None:
        """Replace any unread state in the queue with the newest one."""
        self._last_step_state = step_state
        try:
            self._state_queue.get_nowait()
        except queue.Empty:
            pass
        self._state_queue.put(step_state)

    def _compute_yaw_error(self, raw_state: Any, data: StateData) -> float:
        """Signed heading error: track yaw minus car yaw, wrapped to [-π, π]."""
        pos = get_position(raw_state)
        track_fwd = self.centerline.forward_at(pos)
        track_yaw = math.atan2(float(track_fwd[0]), float(track_fwd[2]))
        car_yaw = data.rotation.yaw()
        diff = (track_yaw - car_yaw + math.pi) % (2 * math.pi) - math.pi
        return diff
