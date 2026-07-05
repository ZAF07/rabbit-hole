"""In-memory fakes of the reader's ports — the fast test substrate.

The same behavioral suite runs against these fakes and the Postgres adapters,
so the two can never silently diverge.
"""

from consumption.domain.identity import User
from consumption.domain.journey import Journey
from consumption.domain.session import Session
from consumption.ports.session_repository import SessionRepository
from consumption.ports.user_repository import UserRepository


class InMemoryUserRepository(UserRepository):
    """Dict-backed identity store, semantics-identical to Postgres."""

    def __init__(self) -> None:
        """Create an empty identity store."""
        self._users: dict[str, User] = {}

    def add(self, user: User) -> None:
        """Persist a User; idempotent by id.

        Args:
            user: The User to persist.
        """
        self._users[user.id] = user

    def get(self, user_id: str) -> User | None:
        """Fetch a User by identity.

        Args:
            user_id: The identity to resolve.

        Returns:
            The User, or None if absent.
        """
        return self._users.get(user_id)


class InMemorySessionRepository(SessionRepository):
    """Dict-backed path + Session store, semantics-identical to Postgres."""

    def __init__(self) -> None:
        """Create an empty path and Session store."""
        self._journeys: dict[str, Journey] = {}
        self._sessions: dict[str, Session] = {}

    def get_journey(self, user_id: str) -> Journey | None:
        """Fetch a User's durable Journey.

        Args:
            user_id: The owner of the path.

        Returns:
            The Journey, or None if never started.
        """
        return self._journeys.get(user_id)

    def save_journey(self, journey: Journey) -> None:
        """Persist a User's durable Journey; idempotent by user id.

        Args:
            journey: The path to persist.
        """
        self._journeys[journey.user_id] = journey

    def save_session(self, session: Session) -> None:
        """Persist an analytics Session; idempotent by id.

        Args:
            session: The Session to persist.
        """
        self._sessions[session.id] = session

    def get_current_session(self, user_id: str) -> Session | None:
        """Fetch a User's most recent analytics Session.

        Args:
            user_id: The reader whose window to resolve.

        Returns:
            The most recent Session (open preferred on a tie), or None.
        """
        candidates = [s for s in self._sessions.values() if s.user_id == user_id]
        if not candidates:
            return None
        return max(candidates, key=lambda s: (s.started_at, s.ended_at is None))
