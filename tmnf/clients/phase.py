from enum import Enum, auto


VELOCITY_ZERO_THRESHOLD = 0.5   # m/s
PAUSE_DURATION_MS = 2_000       # game milliseconds


class Phase(Enum):
    BRAKING_START = auto()
    PAUSE_START   = auto()
    RUNNING       = auto()
    BRAKING_END   = auto()
    PAUSE_END     = auto()
    DONE          = auto()
