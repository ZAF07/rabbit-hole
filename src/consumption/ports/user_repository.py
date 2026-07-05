"""The UserRepository port — the reader's identity store."""

from abc import ABC, abstractmethod

from consumption.domain.identity import User


class UserRepository(ABC):
    """Durable store for reader identities."""

    @abstractmethod
    def add(self, user: User) -> None:
        """Persist a User; idempotent by ``user.id``.

        Args:
            user: The User to persist.
        """

    @abstractmethod
    def get(self, user_id: str) -> User | None:
        """Fetch a User by identity.

        Args:
            user_id: The identity to resolve.

        Returns:
            The User, or None if no such User exists.
        """
