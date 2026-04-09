"""PhaseAwareClient — base class for all TMNF TMInterface clients.

Provides the shared phase state machine fields and _transition() helper so
each concrete client only implements the phase-specific driving logic.
"""

from tminterface.client import Client

from clients.phase import Phase


class PhaseAwareClient(Client):
    """Base class that owns _phase/_phase_start_ms and the _transition() helper.

    All three client types (InstructionClient, AdaptiveClient, RLClient) follow
    the same phase lifecycle.  Rather than duplicating the fields and the
    transition method in each class, they inherit from here.
    """

    def __init__(self) -> None:
        super().__init__()
        self._phase: Phase = Phase.BRAKING_START
        self._phase_start_ms: int = 0

    def _transition(self, phase: Phase, current_time_ms: int) -> None:
        """Log and apply a phase transition."""
        print(f"Phase: {self._phase.name} -> {phase.name}")
        self._phase = phase
        self._phase_start_ms = current_time_ms
