from tminterface.client import Client
from tminterface.interface import TMInterface

from clients.base import Phase, PhaseAwareClient
from instructions import InputState, apply_action, parse_instructions
from track import Centerline
from utils import StateData


VELOCITY_ZERO_THRESHOLD = 0.5   # m/s
PAUSE_DURATION_MS = 2_000       # game milliseconds


class InstructionClient(PhaseAwareClient):
    """Use a file like runs/example_run.txt to give simple instructions of when to steer, accelerate etc."""

    def __init__(self, instruction_file: str, centerline_file: str | None = None, speed: float = 1.0) -> None:
        super().__init__()
        self.speed = speed
        self.instructions = parse_instructions(instruction_file)
        self.centerline = Centerline(centerline_file) if centerline_file else None
        self._next_idx: int = 0
        self._input = InputState()
        self._ticks_idx = 0

    def on_registered(self, iface: TMInterface) -> None:
        print(f"Connected. Running {len(self.instructions)} instruction(s) at speed {self.speed}x.")
        iface.execute_command(f"set speed {self.speed}")

    def on_run_step(self, iface: TMInterface, _time: int) -> None:
        state = iface.get_simulation_state()
        data = StateData(state, centerline=self.centerline)
        speed = data.velocity.magnitude()

        self._ticks_idx += 1
        if self._ticks_idx % 100 == 0:
            print(data)

        match self._phase:
            case Phase.BRAKING_START:
                self._input = InputState(brake=True)
                if speed < VELOCITY_ZERO_THRESHOLD:
                    self._transition(Phase.PAUSE_START, _time)

            case Phase.PAUSE_START:
                self._input = InputState()
                if _time - self._phase_start_ms >= PAUSE_DURATION_MS:
                    self._next_idx = 0
                    self._input = InputState()
                    self._transition(Phase.RUNNING, _time)

            case Phase.RUNNING:
                elapsed_s = (_time - self._phase_start_ms) / 1000.0
                while (
                    self._next_idx < len(self.instructions)
                    and self.instructions[self._next_idx].time_s <= elapsed_s
                ):
                    instr = self.instructions[self._next_idx]
                    print(f"[t={elapsed_s:.2f}s] {instr.action}")
                    apply_action(instr.action, self._input)
                    self._next_idx += 1

                if self._next_idx >= len(self.instructions):
                    self._input = InputState(brake=True)
                    self._transition(Phase.BRAKING_END, _time)

            case Phase.BRAKING_END:
                self._input = InputState(brake=True)
                if speed < VELOCITY_ZERO_THRESHOLD:
                    self._transition(Phase.PAUSE_END, _time)

            case Phase.PAUSE_END:
                self._input = InputState()
                if _time - self._phase_start_ms >= PAUSE_DURATION_MS:
                    self._transition(Phase.DONE, _time)
                    print("Run complete.")

            case Phase.DONE:
                self._input = InputState()

        iface.set_input_state(
            accelerate=self._input.accelerate,
            brake=self._input.brake,
            steer=self._input.steer,
        )
