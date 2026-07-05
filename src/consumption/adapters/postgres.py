"""Postgres adapters for the reader's identity and path ports.

Whether these point at local Docker or Supabase is decided entirely by the
connection config (config.py / .env) — swapping stores is never a code change.
These are the reader's *own* tables; the shared Content Graph is a separate
store the reader only ever reads through its port (ADR 0006).
"""

from types import TracebackType
from typing import Any

import psycopg
from psycopg.types.json import Jsonb

from consumption.config import ConsumptionConfig
from consumption.domain.identity import User
from consumption.domain.journey import Edge, Journey
from consumption.domain.session import Session
from consumption.ports.session_repository import SessionRepository
from consumption.ports.user_repository import UserRepository


class _ConnectionHolder:
    """Shared connection lifecycle for the reader's Postgres adapters."""

    def __init__(self, conn: psycopg.Connection[Any]) -> None:
        """Wrap an open connection; the caller owns its lifecycle.

        Args:
            conn: An open psycopg connection to a migrated database.
        """
        self._conn = conn

    def close(self) -> None:
        """Close the underlying connection."""
        self._conn.close()

    def __enter__(self) -> "_ConnectionHolder":
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


class PostgresUserRepository(_ConnectionHolder, UserRepository):
    """Identity store backed by a Postgres connection."""

    @classmethod
    def from_config(cls, config: ConsumptionConfig) -> "PostgresUserRepository":
        """Open a connection from config and wrap it.

        Args:
            config: The reader store's connection configuration.

        Returns:
            A repository owning a newly opened connection.
        """
        return cls(psycopg.connect(config.dsn))

    def add(self, user: User) -> None:
        """Persist a User; idempotent by id.

        Args:
            user: The User to persist.
        """
        with self._conn.transaction():
            self._conn.execute(
                "INSERT INTO users (id) VALUES (%s) ON CONFLICT (id) DO NOTHING",
                (user.id,),
            )

    def get(self, user_id: str) -> User | None:
        """Fetch a User by identity.

        Args:
            user_id: The identity to resolve.

        Returns:
            The User, or None if absent.
        """
        row = self._conn.execute("SELECT id FROM users WHERE id = %s", (user_id,)).fetchone()
        return User(id=row[0]) if row is not None else None


class PostgresSessionRepository(_ConnectionHolder, SessionRepository):
    """Path + analytics-Session store backed by a Postgres connection."""

    @classmethod
    def from_config(cls, config: ConsumptionConfig) -> "PostgresSessionRepository":
        """Open a connection from config and wrap it.

        Args:
            config: The reader store's connection configuration.

        Returns:
            A repository owning a newly opened connection.
        """
        return cls(psycopg.connect(config.dsn))

    def get_journey(self, user_id: str) -> Journey | None:
        """Fetch a User's durable Journey.

        Args:
            user_id: The owner of the path.

        Returns:
            The Journey, or None if never started.
        """
        row = self._conn.execute(
            "SELECT stack FROM journeys WHERE user_id = %s", (user_id,)
        ).fetchone()
        if row is None:
            return None
        nodes = self._conn.execute(
            "SELECT piece_id FROM journey_nodes WHERE user_id = %s ORDER BY ordinal",
            (user_id,),
        ).fetchall()
        edges = self._conn.execute(
            "SELECT from_piece_id, to_piece_id FROM journey_edges"
            " WHERE user_id = %s ORDER BY ordinal",
            (user_id,),
        ).fetchall()
        return Journey(
            user_id=user_id,
            stack=tuple(row[0]),
            visited=tuple(node[0] for node in nodes),
            pulled=tuple(Edge(from_piece_id=edge[0], to_piece_id=edge[1]) for edge in edges),
        )

    def save_journey(self, journey: Journey) -> None:
        """Persist a User's durable Journey; idempotent by user id.

        Rewrites the stack, nodes, and edges wholesale so the stored path
        always matches the given Journey exactly.

        Args:
            journey: The path to persist.
        """
        with self._conn.transaction():
            self._conn.execute(
                "INSERT INTO journeys (user_id, stack) VALUES (%s, %s)"
                " ON CONFLICT (user_id) DO UPDATE SET stack = EXCLUDED.stack, updated_at = now()",
                (journey.user_id, Jsonb(list(journey.stack))),
            )
            self._conn.execute("DELETE FROM journey_nodes WHERE user_id = %s", (journey.user_id,))
            self._conn.execute("DELETE FROM journey_edges WHERE user_id = %s", (journey.user_id,))
            with self._conn.cursor() as cur:
                cur.executemany(
                    "INSERT INTO journey_nodes (user_id, piece_id, ordinal) VALUES (%s, %s, %s)",
                    [
                        (journey.user_id, piece_id, ordinal)
                        for ordinal, piece_id in enumerate(journey.visited)
                    ],
                )
                cur.executemany(
                    "INSERT INTO journey_edges"
                    " (user_id, from_piece_id, to_piece_id, ordinal) VALUES (%s, %s, %s, %s)",
                    [
                        (journey.user_id, edge.from_piece_id, edge.to_piece_id, ordinal)
                        for ordinal, edge in enumerate(journey.pulled)
                    ],
                )

    def save_session(self, session: Session) -> None:
        """Persist an analytics Session; idempotent by id.

        Args:
            session: The Session to persist.
        """
        with self._conn.transaction():
            self._conn.execute(
                "INSERT INTO sessions (id, user_id, started_at, last_activity_at, ended_at)"
                " VALUES (%s, %s, %s, %s, %s)"
                " ON CONFLICT (id) DO UPDATE SET"
                "  last_activity_at = EXCLUDED.last_activity_at,"
                "  ended_at = EXCLUDED.ended_at",
                (
                    session.id,
                    session.user_id,
                    session.started_at,
                    session.last_activity_at,
                    session.ended_at,
                ),
            )

    def get_current_session(self, user_id: str) -> Session | None:
        """Fetch a User's most recent analytics Session.

        The current Session is the one that opened most recently; an open
        Session is preferred over a closed one on a tie.

        Args:
            user_id: The reader whose window to resolve.

        Returns:
            The most recent Session, or None.
        """
        row = self._conn.execute(
            "SELECT id, user_id, started_at, last_activity_at, ended_at FROM sessions"
            " WHERE user_id = %s"
            " ORDER BY started_at DESC, (ended_at IS NULL) DESC"
            " LIMIT 1",
            (user_id,),
        ).fetchone()
        if row is None:
            return None
        return Session(
            id=row[0],
            user_id=row[1],
            started_at=row[2],
            last_activity_at=row[3],
            ended_at=row[4],
        )
