"""Session — the analytics window over a reader's durable Journey.

A Session is the time-bounded engagement window, distinct from the durable
Journey it observes (ADR 0008). It ends on a hybrid rule — inactivity beyond a
timeout **or** an explicit app close, whichever comes first. The Journey
outlives it: resuming after a gap begins a *new* Session that continues the
*same* path.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

INACTIVITY_TIMEOUT = timedelta(minutes=30)


@dataclass(frozen=True)
class Session:
    """One analytics window over a User's Journey.

    Attributes:
        id: The Session's identity — a fresh one is minted whenever a new
            window opens (so resuming after a gap is observably a new Session).
        user_id: The reader this window belongs to.
        started_at: When the window opened.
        last_activity_at: When the reader last acted within the window; the
            inactivity timeout is measured from here.
        ended_at: When the window closed (explicit app close, or the moment the
            timeout was recognized), or None while it is still open.
    """

    id: str
    user_id: str
    started_at: datetime
    last_activity_at: datetime
    ended_at: datetime | None = None

    def is_expired(self, now: datetime, timeout: timedelta = INACTIVITY_TIMEOUT) -> bool:
        """Whether this window has closed by ``now``.

        Args:
            now: The current instant.
            timeout: The inactivity budget; defaults to the ~30-minute rule.

        Returns:
            True if the Session was explicitly ended or has been inactive for
            at least ``timeout``.
        """
        return self.ended_at is not None or (now - self.last_activity_at) >= timeout
