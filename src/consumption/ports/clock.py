"""The Clock port — the reader's only source of the current instant.

Time is a dependency, injected like any other, so the Session-boundary logic
is deterministic under test. Production wires a system clock; tests wire a
clock they advance by hand.
"""

from abc import ABC, abstractmethod
from datetime import datetime


class Clock(ABC):
    """A source of the current instant."""

    @abstractmethod
    def now(self) -> datetime:
        """Return the current instant as a timezone-aware datetime."""
