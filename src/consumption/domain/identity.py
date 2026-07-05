"""User — the reader's identity.

V1 personalizes nothing, but it still needs per-user identity so the durable
Session path has an owner and Phase-2 personalization has a substrate to read
(ADR 0008). The User is kept strictly distinct from their Personal Knowledge
Graph: this is the identity, that is the accumulated trail.
"""

from dataclasses import dataclass

from consumption.domain.errors import ConsumptionError


class UserValidationError(ConsumptionError, ValueError):
    """A User violates its own construction contract."""


@dataclass(frozen=True)
class User:
    """A person with an account.

    Attributes:
        id: Caller-supplied identity; the owner of a Journey and its Sessions.
    """

    id: str

    def __post_init__(self) -> None:
        """Validate that the identity is non-empty.

        Raises:
            UserValidationError: If the id is blank.
        """
        if not self.id or not self.id.strip():
            raise UserValidationError("User requires a non-empty id")
