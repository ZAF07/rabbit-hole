"""The SessionRepository port — the reader's durable path store.

Persists the durable Journey (path + backtrack stack) per User. The path is
recorded from V1 even though nothing personalizes yet: recording is not
personalizing (ADR 0008). The analytics-Session boundary is layered on top of
this same port.
"""

from abc import ABC, abstractmethod

from consumption.domain.journey import Journey
from consumption.domain.session import Session


class SessionRepository(ABC):
    """Durable store for the reader's Journey and analytics Sessions."""

    @abstractmethod
    def get_journey(self, user_id: str) -> Journey | None:
        """Fetch a User's durable Journey.

        Args:
            user_id: The owner of the path.

        Returns:
            The Journey, or None if the User has not started one.
        """

    @abstractmethod
    def save_journey(self, journey: Journey) -> None:
        """Persist a User's durable Journey; idempotent by ``journey.user_id``.

        Args:
            journey: The path to persist, replacing any prior state.
        """

    @abstractmethod
    def save_session(self, session: Session) -> None:
        """Persist an analytics Session; idempotent by ``session.id``.

        Args:
            session: The Session to persist, replacing any prior state.
        """

    @abstractmethod
    def get_current_session(self, user_id: str) -> Session | None:
        """Fetch a User's most recent analytics Session.

        The current Session is the one that opened most recently; on a tie an
        open Session is preferred over a closed one.

        Args:
            user_id: The reader whose window to resolve.

        Returns:
            The most recent Session, or None if the User has none.
        """
