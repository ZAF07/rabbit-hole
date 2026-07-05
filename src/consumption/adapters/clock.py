"""System clock adapter — production's source of the current instant."""

from datetime import UTC, datetime

from consumption.ports.clock import Clock


class SystemClock(Clock):
    """A Clock reading the real wall clock in UTC."""

    def now(self) -> datetime:
        """Return the current instant as a timezone-aware UTC datetime."""
        return datetime.now(UTC)
