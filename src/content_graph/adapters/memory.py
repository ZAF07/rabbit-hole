"""In-memory fake of the ContentGraphRepository port.

The fast test substrate the other tracks build on. The shared contract-test
suite runs against both this fake and the Postgres adapter, so the two can
never silently diverge.
"""

from collections.abc import Sequence
from datetime import date

from content_graph.domain.connection import Connection
from content_graph.domain.errors import PieceNotFoundError, TopicNotFoundError
from content_graph.domain.piece import Piece
from content_graph.domain.read_models import (
    ConnectionPreview,
    PieceRead,
    PieceSummary,
    TopicRead,
)
from content_graph.domain.topic import Topic
from content_graph.ports.repository import ContentGraphRepository


class InMemoryContentGraphRepository(ContentGraphRepository):
    """Dict-backed implementation of the port, semantics-identical to Postgres."""

    def __init__(self) -> None:
        """Create an empty store."""
        self._pieces: dict[str, Piece] = {}
        self._topics: dict[str, Topic] = {}
        self._topic_parents: dict[str, frozenset[str]] = {}
        self._connections: dict[tuple[str, str], Connection] = {}
        self._daily_features: dict[date, str] = {}

    def upsert_piece(self, piece: Piece) -> None:
        """Write a Piece with its ordered blocks and Topic tags; idempotent by id.

        Args:
            piece: The Piece to persist.

        Raises:
            TopicNotFoundError: If any tagged Topic id does not exist.
        """
        missing = [tid for tid in piece.topic_ids if tid not in self._topics]
        if missing:
            raise TopicNotFoundError(f"unknown Topic ids: {missing}")
        self._pieces[piece.id] = piece

    def upsert_topic(self, topic: Topic) -> None:
        """Write a Topic; idempotent by ``topic.id``.

        Args:
            topic: The Topic to persist.
        """
        self._topics[topic.id] = topic

    def set_topic_parents(self, topic_id: str, parent_ids: Sequence[str]) -> None:
        """Replace a Topic's full parent set.

        Args:
            topic_id: The child Topic.
            parent_ids: The complete new set of parent Topic ids.

        Raises:
            TopicNotFoundError: If the child or any parent does not exist.
        """
        missing = [tid for tid in (topic_id, *parent_ids) if tid not in self._topics]
        if missing:
            raise TopicNotFoundError(f"unknown Topic ids: {missing}")
        self._topic_parents[topic_id] = frozenset(parent_ids)

    def upsert_connection(self, connection: Connection) -> None:
        """Write a directed Connection; idempotent by ``(from, to)`` identity.

        Args:
            connection: The edge to persist.

        Raises:
            PieceNotFoundError: If either endpoint Piece does not exist.
        """
        missing = [
            pid
            for pid in (connection.from_piece_id, connection.to_piece_id)
            if pid not in self._pieces
        ]
        if missing:
            raise PieceNotFoundError(f"unknown Piece ids: {missing}")
        self._connections[(connection.from_piece_id, connection.to_piece_id)] = connection

    def get_connections_from(self, piece_id: str) -> tuple[ConnectionPreview, ...]:
        """Fetch a Piece's outbound Connections, preview-ready.

        Args:
            piece_id: The origin Piece.

        Returns:
            One preview per outbound edge, ordered by destination id.
        """
        outbound = sorted(
            (conn for conn in self._connections.values() if conn.from_piece_id == piece_id),
            key=lambda conn: conn.to_piece_id,
        )
        return tuple(
            ConnectionPreview(
                from_piece_id=conn.from_piece_id,
                to_piece_id=conn.to_piece_id,
                hook=conn.hook,
                to_title=self._pieces[conn.to_piece_id].title,
                to_topics=self._topic_reads(self._pieces[conn.to_piece_id].topic_ids),
            )
            for conn in outbound
        )

    def get_connections_to(self, piece_id: str) -> tuple[Connection, ...]:
        """Fetch a Piece's inbound Connections.

        Args:
            piece_id: The destination Piece.

        Returns:
            The inbound edges, ordered by origin id.
        """
        return tuple(
            sorted(
                (conn for conn in self._connections.values() if conn.to_piece_id == piece_id),
                key=lambda conn: conn.from_piece_id,
            )
        )

    def get_topics_for(self, piece_ids: Sequence[str]) -> dict[str, tuple[TopicRead, ...]]:
        """Look up the Topics (each with its parents) for a set of Pieces.

        Args:
            piece_ids: The Pieces to resolve.

        Returns:
            One entry per existing piece id; unknown ids are absent.
        """
        return {
            piece_id: self._topic_reads(self._pieces[piece_id].topic_ids)
            for piece_id in piece_ids
            if piece_id in self._pieces
        }

    def get_topic(self, topic_id: str) -> TopicRead | None:
        """Fetch a single Topic with its parents.

        Args:
            topic_id: The Topic identity to resolve.

        Returns:
            The Topic read model, or None if no such Topic exists.
        """
        reads = self._topic_reads([topic_id])
        return reads[0] if reads else None

    def list_piece_summaries(self) -> tuple[PieceSummary, ...]:
        """List every stored Piece as an entry-surface summary.

        Returns:
            One summary per stored Piece, ordered by id.
        """
        ordered = sorted(self._pieces)
        summaries = self.get_piece_summaries(ordered)
        return tuple(summaries[piece_id] for piece_id in ordered)

    def get_piece_summaries(self, piece_ids: Sequence[str]) -> dict[str, PieceSummary]:
        """Fetch entry-surface summaries (teaser, Topics, no body) for Pieces.

        Args:
            piece_ids: The Pieces to resolve.

        Returns:
            One entry per existing piece id; unknown ids are absent.
        """
        return {
            piece_id: PieceSummary(
                id=piece.id,
                title=piece.title,
                teaser=piece.teaser,
                read_time_min=piece.read_time_min,
                topics=self._topic_reads(piece.topic_ids),
            )
            for piece_id in piece_ids
            if (piece := self._pieces.get(piece_id)) is not None
        }

    def set_daily_feature(self, on: date, piece_id: str) -> None:
        """Point a date's headline slot at a Piece; idempotent by date.

        Args:
            on: The date the Piece fronts the app.
            piece_id: The Piece to promote.

        Raises:
            PieceNotFoundError: If the Piece does not exist.
        """
        if piece_id not in self._pieces:
            raise PieceNotFoundError(f"unknown Piece ids: [{piece_id!r}]")
        self._daily_features[on] = piece_id

    def get_daily_feature(self, on: date | None = None) -> PieceRead | None:
        """Fetch the Piece assigned to the most recent date on or before ``on``.

        Args:
            on: The date to resolve for; defaults to today.

        Returns:
            The featured Piece's read model, or None if never assigned.
        """
        resolve_on = date.today() if on is None else on
        eligible = [assigned for assigned in self._daily_features if assigned <= resolve_on]
        if not eligible:
            return None
        return self.get_piece(self._daily_features[max(eligible)])

    def get_piece(self, piece_id: str) -> PieceRead | None:
        """Fetch a single Piece with its full ordered body and Topics.

        Args:
            piece_id: The Piece identity to resolve.

        Returns:
            The Piece read model without generation-only fields, or None.
        """
        piece = self._pieces.get(piece_id)
        if piece is None:
            return None
        return PieceRead(
            id=piece.id,
            title=piece.title,
            teaser=piece.teaser,
            read_time_min=piece.read_time_min,
            blocks=tuple(piece.blocks),
            topics=self._topic_reads(piece.topic_ids),
        )

    def _topic_reads(self, topic_ids: Sequence[str]) -> tuple[TopicRead, ...]:
        """Build TopicRead models, sorted by slug, parents sorted by id.

        Args:
            topic_ids: The Topic ids to materialize.

        Returns:
            The read models for every id present in the store.
        """
        topics = sorted(
            (self._topics[tid] for tid in topic_ids if tid in self._topics),
            key=lambda topic: topic.slug,
        )
        return tuple(
            TopicRead(
                id=topic.id,
                slug=topic.slug,
                title=topic.title,
                parent_ids=tuple(sorted(self._topic_parents.get(topic.id, frozenset()))),
            )
            for topic in topics
        )
