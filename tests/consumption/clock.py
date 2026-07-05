"""A hand-advanced Clock for deterministic Session-boundary tests."""

from datetime import UTC, datetime, timedelta

from consumption.ports.clock import Clock


class MutableClock(Clock):
    """A Clock the test advances by hand, so time is fully deterministic."""

    def __init__(self, start: datetime | None = None) -> None:
        """Start the clock at a fixed instant.

        Args:
            start: The initial instant; defaults to a fixed UTC datetime.
        """
        self._now = start or datetime(2026, 7, 5, 9, 0, tzinfo=UTC)

    def now(self) -> datetime:
        """Return the current instant."""
        return self._now

    def advance(self, delta: timedelta) -> None:
        """Move the clock forward.

        Args:
            delta: How far to advance.
        """
        self._now += delta
