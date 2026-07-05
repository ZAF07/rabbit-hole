"""The ContentGraphRepository port — the physical seam of ADR 0006.

One shared port with a write surface (generation publishes, and reads at plan
time for dedup) and a read surface (consumption renders). Consumption never
writes; that split is enforced by convention and review — each subsystem's
composition wires only its own half.
"""

from abc import ABC, abstractmethod
from collections.abc import Sequence
from datetime import date

from content_graph.domain.connection import Connection
from content_graph.domain.piece import Piece
from content_graph.domain.read_models import (
    ConnectionPreview,
    PieceRead,
    PieceSummary,
    TopicRead,
)
from content_graph.domain.topic import Topic


class ContentGraphRepository(ABC):
    """Single access port to the Content Graph store."""

    @abstractmethod
    def upsert_piece(self, piece: Piece) -> None:
        """Write a Piece with its ordered blocks and Topic tags; idempotent by id.

        Re-writing an existing id replaces the Piece's fields, body, and
        tags without creating duplicates.

        Args:
            piece: The Piece to persist, body already validated at
                construction time.

        Raises:
            TopicNotFoundError: If any tagged Topic id does not exist.
        """

    @abstractmethod
    def upsert_topic(self, topic: Topic) -> None:
        """Write a Topic; idempotent by ``topic.id``.

        Args:
            topic: The Topic to persist.
        """

    @abstractmethod
    def set_topic_parents(self, topic_id: str, parent_ids: Sequence[str]) -> None:
        """Replace a Topic's full parent set — zero or more parents (the DAG).

        Args:
            topic_id: The child Topic.
            parent_ids: The complete new set of parent Topic ids.

        Raises:
            TopicNotFoundError: If the child or any parent does not exist.
        """

    @abstractmethod
    def upsert_connection(self, connection: Connection) -> None:
        """Write a directed Connection; idempotent by ``(from, to)`` identity.

        Re-writing an existing edge replaces its hook without duplicating
        the edge.

        Args:
            connection: The edge to persist, hook already validated at
                construction time.

        Raises:
            PieceNotFoundError: If either endpoint Piece does not exist —
                dead links can never be stored (invariant I5's backstop).
        """

    @abstractmethod
    def get_connections_from(self, piece_id: str) -> tuple[ConnectionPreview, ...]:
        """Fetch a Piece's outbound Connections, preview-ready.

        Args:
            piece_id: The origin Piece.

        Returns:
            One preview per outbound edge — hook plus the destination's
            title and Topics — ordered by destination id.
        """

    @abstractmethod
    def get_connections_to(self, piece_id: str) -> tuple[Connection, ...]:
        """Fetch a Piece's inbound Connections.

        Together with :meth:`get_connections_from`, this lets
        constellation-level checks (dead-ends, connectedness) and the
        Personal Knowledge Graph be computed.

        Args:
            piece_id: The destination Piece.

        Returns:
            The inbound edges, ordered by origin id.
        """

    @abstractmethod
    def get_topics_for(self, piece_ids: Sequence[str]) -> dict[str, tuple[TopicRead, ...]]:
        """Look up the Topics (each with its parents) for a set of Pieces.

        Args:
            piece_ids: The Pieces to resolve.

        Returns:
            A mapping with one entry per piece id that exists in the store —
            an empty tuple for untagged Pieces; unknown ids are absent.
        """

    @abstractmethod
    def get_piece_summaries(self, piece_ids: Sequence[str]) -> dict[str, PieceSummary]:
        """Fetch entry-surface summaries (teaser, Topics, no body) for Pieces.

        Args:
            piece_ids: The Pieces to resolve.

        Returns:
            A mapping with one entry per piece id that exists in the store;
            unknown ids are absent.
        """

    @abstractmethod
    def set_daily_feature(self, on: date, piece_id: str) -> None:
        """Point a date's headline slot at a Piece; idempotent by date.

        The Daily Feature is a scheduling role, not a kind of Piece —
        re-assigning a date replaces its pointer.

        Args:
            on: The date the Piece fronts the app.
            piece_id: The Piece to promote.

        Raises:
            PieceNotFoundError: If the Piece does not exist.
        """

    @abstractmethod
    def get_daily_feature(self, on: date | None = None) -> PieceRead | None:
        """Fetch the current Daily Feature Piece — the app's front door.

        The pointer assigned to the most recent date on or before ``on``
        wins, so a missed day never blanks the front door; future
        assignments are not surfaced early.

        Args:
            on: The date to resolve for; defaults to today.

        Returns:
            The featured Piece's read model, or None if nothing has ever
            been assigned on or before ``on``.
        """

    @abstractmethod
    def get_piece(self, piece_id: str) -> PieceRead | None:
        """Fetch a single Piece with its full ordered body.

        Args:
            piece_id: The Piece identity to resolve.

        Returns:
            The Piece read model, or None if no such Piece exists. The read
            model contains no generation-only field (ADR 0006).
        """
