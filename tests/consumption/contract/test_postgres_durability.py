"""Issue 05 — the reader's own tables durably survive across connections.

The parametrized suite already runs the whole reader loop against Postgres.
These tests add the last mile: that committed identity, path, and Session state
are read back intact through a *separate* connection — genuine durability, not
read-your-own-writes.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

import psycopg

from consumption.adapters.postgres import (
    PostgresSessionRepository,
    PostgresUserRepository,
)
from consumption.domain.identity import User
from consumption.domain.journey import Edge, Journey
from consumption.domain.session import Session

_START = datetime(2026, 7, 5, 9, 0, tzinfo=UTC)


def test_journey_round_trips_through_a_separate_connection(
    clean_pg: psycopg.Connection[Any], pg_dsn: str
) -> None:
    PostgresUserRepository(clean_pg).add(User(id="user-ada"))
    journey = Journey(
        user_id="user-ada",
        stack=("piece-a", "piece-c"),
        visited=("piece-a", "piece-b", "piece-c"),
        pulled=(Edge("piece-a", "piece-b"), Edge("piece-a", "piece-c")),
    )
    PostgresSessionRepository(clean_pg).save_journey(journey)

    with psycopg.connect(pg_dsn) as conn:
        restored = PostgresSessionRepository(conn).get_journey("user-ada")

    assert restored == journey  # stack, deduped nodes, and pulled edges all intact


def test_current_session_round_trips_through_a_separate_connection(
    clean_pg: psycopg.Connection[Any], pg_dsn: str
) -> None:
    PostgresUserRepository(clean_pg).add(User(id="user-ada"))
    sessions = PostgresSessionRepository(clean_pg)
    older = Session("s1", "user-ada", _START, _START, ended_at=_START + timedelta(minutes=10))
    newer = Session("s2", "user-ada", _START + timedelta(hours=1), _START + timedelta(hours=1))
    sessions.save_session(older)
    sessions.save_session(newer)

    with psycopg.connect(pg_dsn) as conn:
        current = PostgresSessionRepository(conn).get_current_session("user-ada")

    assert current is not None
    assert current.id == "s2"  # the most recently opened window wins
    assert current.ended_at is None
    assert current.started_at == newer.started_at
