"""Postgres adapter for the ContentGraphRepository port.

Whether this points at local Docker or Supabase is decided entirely by the
connection config (config.py / .env) — swapping stores is never a code change.
"""

from collections.abc import Sequence
from datetime import date
from types import TracebackType
from typing import Any

import psycopg
from psycopg import errors
from psycopg.types.json import Jsonb

from content_graph.config import ContentGraphConfig
from content_graph.domain.blocks import BlockKind, ContentBlock
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


class PostgresContentGraphRepository(ContentGraphRepository):
    """Port implementation backed by a Postgres connection."""

    def __init__(self, conn: psycopg.Connection[Any]) -> None:
        """Wrap an open connection; the caller owns its lifecycle.

        Args:
            conn: An open psycopg connection to a migrated database.
        """
        self._conn = conn

    @classmethod
    def from_config(cls, config: ContentGraphConfig) -> "PostgresContentGraphRepository":
        """Open a connection from config and wrap it.

        Args:
            config: The store's connection configuration.

        Returns:
            A repository owning a newly opened connection; close it with
            :meth:`close` or by using the repository as a context manager.
        """
        return cls(psycopg.connect(config.dsn))

    def close(self) -> None:
        """Close the underlying connection."""
        self._conn.close()

    def __enter__(self) -> "PostgresContentGraphRepository":
        """Return self for use as a context manager."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        """Close the connection on context exit."""
        self.close()

    def upsert_piece(self, piece: Piece) -> None:
        """Write a Piece with its ordered blocks and Topic tags; idempotent by id.

        Args:
            piece: The Piece to persist.

        Raises:
            TopicNotFoundError: If any tagged Topic id does not exist.
        """
        try:
            with self._conn.transaction():
                self._conn.execute(
                    "INSERT INTO pieces (id, title, teaser, read_time_min, run_id)"
                    " VALUES (%s, %s, %s, %s, %s)"
                    " ON CONFLICT (id) DO UPDATE SET"
                    "  title = EXCLUDED.title,"
                    "  teaser = EXCLUDED.teaser,"
                    "  read_time_min = EXCLUDED.read_time_min,"
                    "  run_id = EXCLUDED.run_id,"
                    "  updated_at = now()",
                    (piece.id, piece.title, piece.teaser, piece.read_time_min, piece.run_id),
                )
                self._conn.execute("DELETE FROM blocks WHERE piece_id = %s", (piece.id,))
                self._conn.execute("DELETE FROM piece_topics WHERE piece_id = %s", (piece.id,))
                with self._conn.cursor() as cur:
                    cur.executemany(
                        "INSERT INTO blocks (piece_id, ordinal, kind, payload)"
                        " VALUES (%s, %s, %s, %s)",
                        [
                            (piece.id, ordinal, block.kind.value, Jsonb(dict(block.payload)))
                            for ordinal, block in enumerate(piece.blocks)
                        ],
                    )
                    cur.executemany(
                        "INSERT INTO piece_topics (piece_id, topic_id) VALUES (%s, %s)",
                        [(piece.id, topic_id) for topic_id in piece.topic_ids],
                    )
        except errors.ForeignKeyViolation as exc:
            raise TopicNotFoundError(
                f"Piece {piece.id!r} references a Topic that does not exist:"
                f" {exc.diag.message_detail}"
            ) from exc

    def upsert_topic(self, topic: Topic) -> None:
        """Write a Topic; idempotent by ``topic.id``.

        Args:
            topic: The Topic to persist.
        """
        with self._conn.transaction():
            self._conn.execute(
                "INSERT INTO topics (id, slug, title) VALUES (%s, %s, %s)"
                " ON CONFLICT (id) DO UPDATE SET slug = EXCLUDED.slug, title = EXCLUDED.title",
                (topic.id, topic.slug, topic.title),
            )

    def set_topic_parents(self, topic_id: str, parent_ids: Sequence[str]) -> None:
        """Replace a Topic's full parent set.

        Args:
            topic_id: The child Topic.
            parent_ids: The complete new set of parent Topic ids.

        Raises:
            TopicNotFoundError: If the child or any parent does not exist.
        """
        try:
            with self._conn.transaction():
                child = self._conn.execute(
                    "SELECT 1 FROM topics WHERE id = %s", (topic_id,)
                ).fetchone()
                if child is None:
                    raise TopicNotFoundError(f"unknown Topic ids: [{topic_id!r}]")
                self._conn.execute("DELETE FROM topic_parents WHERE child_id = %s", (topic_id,))
                with self._conn.cursor() as cur:
                    cur.executemany(
                        "INSERT INTO topic_parents (child_id, parent_id) VALUES (%s, %s)",
                        [(topic_id, parent_id) for parent_id in dict.fromkeys(parent_ids)],
                    )
        except errors.ForeignKeyViolation as exc:
            raise TopicNotFoundError(
                f"Topic {topic_id!r} was given a parent that does not exist:"
                f" {exc.diag.message_detail}"
            ) from exc

    def upsert_connection(self, connection: Connection) -> None:
        """Write a directed Connection; idempotent by ``(from, to)`` identity.

        Args:
            connection: The edge to persist.

        Raises:
            PieceNotFoundError: If either endpoint Piece does not exist.
        """
        try:
            with self._conn.transaction():
                self._conn.execute(
                    "INSERT INTO connections (from_piece_id, to_piece_id, hook)"
                    " VALUES (%s, %s, %s)"
                    " ON CONFLICT (from_piece_id, to_piece_id)"
                    " DO UPDATE SET hook = EXCLUDED.hook",
                    (connection.from_piece_id, connection.to_piece_id, connection.hook),
                )
        except errors.ForeignKeyViolation as exc:
            raise PieceNotFoundError(
                f"Connection {connection.from_piece_id!r} -> {connection.to_piece_id!r}"
                f" references a Piece that does not exist: {exc.diag.message_detail}"
            ) from exc

    def get_connections_from(self, piece_id: str) -> tuple[ConnectionPreview, ...]:
        """Fetch a Piece's outbound Connections, preview-ready.

        Args:
            piece_id: The origin Piece.

        Returns:
            One preview per outbound edge, ordered by destination id.
        """
        rows = self._conn.execute(
            "SELECT c.from_piece_id, c.to_piece_id, c.hook, p.title"
            " FROM connections c JOIN pieces p ON p.id = c.to_piece_id"
            " WHERE c.from_piece_id = %s"
            " ORDER BY c.to_piece_id",
            (piece_id,),
        ).fetchall()
        topics = self.get_topics_for([row[1] for row in rows])
        return tuple(
            ConnectionPreview(
                from_piece_id=row[0],
                to_piece_id=row[1],
                hook=row[2],
                to_title=row[3],
                to_topics=topics.get(row[1], ()),
            )
            for row in rows
        )

    def get_connections_to(self, piece_id: str) -> tuple[Connection, ...]:
        """Fetch a Piece's inbound Connections.

        Args:
            piece_id: The destination Piece.

        Returns:
            The inbound edges, ordered by origin id.
        """
        rows = self._conn.execute(
            "SELECT from_piece_id, to_piece_id, hook FROM connections"
            " WHERE to_piece_id = %s ORDER BY from_piece_id",
            (piece_id,),
        ).fetchall()
        return tuple(Connection(*row) for row in rows)

    def get_topics_for(self, piece_ids: Sequence[str]) -> dict[str, tuple[TopicRead, ...]]:
        """Look up the Topics (each with its parents) for a set of Pieces.

        Args:
            piece_ids: The Pieces to resolve.

        Returns:
            One entry per existing piece id; unknown ids are absent.
        """
        ids = list(piece_ids)
        existing = self._conn.execute("SELECT id FROM pieces WHERE id = ANY(%s)", (ids,)).fetchall()
        result: dict[str, tuple[TopicRead, ...]] = {row[0]: () for row in existing}
        rows = self._conn.execute(
            "SELECT pt.piece_id, t.id, t.slug, t.title,"
            "  COALESCE(array_agg(tp.parent_id ORDER BY tp.parent_id)"
            "    FILTER (WHERE tp.parent_id IS NOT NULL), '{}') AS parent_ids"
            " FROM piece_topics pt"
            " JOIN topics t ON t.id = pt.topic_id"
            " LEFT JOIN topic_parents tp ON tp.child_id = t.id"
            " WHERE pt.piece_id = ANY(%s)"
            " GROUP BY pt.piece_id, t.id, t.slug, t.title"
            " ORDER BY pt.piece_id, t.slug",
            (ids,),
        ).fetchall()
        for piece_id, topic_id, slug, title, parent_ids in rows:
            read = TopicRead(id=topic_id, slug=slug, title=title, parent_ids=tuple(parent_ids))
            result[piece_id] = (*result[piece_id], read)
        return result

    def get_piece_summaries(self, piece_ids: Sequence[str]) -> dict[str, PieceSummary]:
        """Fetch entry-surface summaries (teaser, Topics, no body) for Pieces.

        Args:
            piece_ids: The Pieces to resolve.

        Returns:
            One entry per existing piece id; unknown ids are absent.
        """
        ids = list(piece_ids)
        rows = self._conn.execute(
            "SELECT id, title, teaser, read_time_min FROM pieces WHERE id = ANY(%s)",
            (ids,),
        ).fetchall()
        topics = self.get_topics_for([row[0] for row in rows])
        return {
            row[0]: PieceSummary(
                id=row[0],
                title=row[1],
                teaser=row[2],
                read_time_min=row[3],
                topics=topics.get(row[0], ()),
            )
            for row in rows
        }

    def set_daily_feature(self, on: date, piece_id: str) -> None:
        """Point a date's headline slot at a Piece; idempotent by date.

        Args:
            on: The date the Piece fronts the app.
            piece_id: The Piece to promote.

        Raises:
            PieceNotFoundError: If the Piece does not exist.
        """
        try:
            with self._conn.transaction():
                self._conn.execute(
                    "INSERT INTO daily_features (date, piece_id) VALUES (%s, %s)"
                    " ON CONFLICT (date) DO UPDATE SET piece_id = EXCLUDED.piece_id",
                    (on, piece_id),
                )
        except errors.ForeignKeyViolation as exc:
            raise PieceNotFoundError(
                f"Daily Feature points at a Piece that does not exist: {piece_id!r}"
            ) from exc

    def get_daily_feature(self, on: date | None = None) -> PieceRead | None:
        """Fetch the Piece assigned to the most recent date on or before ``on``.

        Args:
            on: The date to resolve for; defaults to today.

        Returns:
            The featured Piece's read model, or None if never assigned.
        """
        resolve_on = date.today() if on is None else on
        row = self._conn.execute(
            "SELECT piece_id FROM daily_features WHERE date <= %s ORDER BY date DESC LIMIT 1",
            (resolve_on,),
        ).fetchone()
        if row is None:
            return None
        return self.get_piece(row[0])

    def get_piece(self, piece_id: str) -> PieceRead | None:
        """Fetch a single Piece with its full ordered body and Topics.

        Args:
            piece_id: The Piece identity to resolve.

        Returns:
            The Piece read model without generation-only fields, or None.
        """
        row = self._conn.execute(
            "SELECT id, title, teaser, read_time_min FROM pieces WHERE id = %s",
            (piece_id,),
        ).fetchone()
        if row is None:
            return None
        return PieceRead(
            id=row[0],
            title=row[1],
            teaser=row[2],
            read_time_min=row[3],
            blocks=self._blocks_for(piece_id),
            topics=self.get_topics_for([piece_id]).get(piece_id, ()),
        )

    def _blocks_for(self, piece_id: str) -> tuple[ContentBlock, ...]:
        """Read a Piece's body in ordinal order.

        Args:
            piece_id: The owning Piece's identity.

        Returns:
            The ordered, typed Content Blocks.
        """
        rows = self._conn.execute(
            "SELECT kind, payload FROM blocks WHERE piece_id = %s ORDER BY ordinal",
            (piece_id,),
        ).fetchall()
        return tuple(ContentBlock(BlockKind(row[0]), row[1]) for row in rows)
