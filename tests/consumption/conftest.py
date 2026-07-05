"""Shared fixtures for the consumption reader suite.

The reader loop runs over an in-memory ``ContentGraphRepository`` seeded with
the fixture constellation. The reader's *own* stores (identity + path) are
parametrized over the in-memory fakes **and** the Postgres adapters, so the
whole behavioural suite runs against both and the two can never silently
diverge — the same contract-test-against-Docker seam the Content Graph uses.
The shared Content Graph stays in-memory throughout: the reader only ever reads
it (ADR 0006); these Postgres tables are the reader's alone.
"""

import os
from collections.abc import Callable, Iterator
from itertools import count
from typing import Any

import psycopg
import pytest
from psycopg import sql
from tests.consumption.clock import MutableClock
from tests.consumption.fixture_constellation import seed

from consumption.adapters.memory import (
    InMemorySessionRepository,
    InMemoryUserRepository,
)
from consumption.adapters.migrate import apply_migrations
from consumption.adapters.postgres import (
    PostgresSessionRepository,
    PostgresUserRepository,
)
from consumption.application.reader import ReaderService
from consumption.ports.session_repository import SessionRepository
from consumption.ports.user_repository import UserRepository
from content_graph.adapters.memory import InMemoryContentGraphRepository
from content_graph.ports.repository import ContentGraphRepository

USER_ID = "user-ada"

TEST_DSN_ENV_VAR = "CONSUMPTION_TEST_DSN"
DEFAULT_TEST_DSN = "postgresql://rabbit:rabbit@localhost:5433/consumption_test"


def _test_dsn() -> str:
    return os.environ.get(TEST_DSN_ENV_VAR, DEFAULT_TEST_DSN)


def _ensure_test_database(dsn: str) -> None:
    """Create the reader's test database if it does not exist yet."""
    params = psycopg.conninfo.conninfo_to_dict(dsn)
    dbname = str(params.get("dbname", ""))
    admin_dsn = psycopg.conninfo.make_conninfo(dsn, dbname="postgres")
    with psycopg.connect(admin_dsn, autocommit=True) as conn:
        exists = conn.execute("SELECT 1 FROM pg_database WHERE datname = %s", (dbname,)).fetchone()
        if not exists:
            conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(dbname)))


@pytest.fixture
def pg_dsn() -> str:
    """The DSN of the reader's Postgres test database."""
    return _test_dsn()


@pytest.fixture(scope="session")
def pg_conn() -> Iterator[psycopg.Connection[Any]]:
    """Session connection to the migrated reader test database."""
    dsn = _test_dsn()
    try:
        _ensure_test_database(dsn)
        conn = psycopg.connect(dsn)
    except psycopg.OperationalError as exc:
        pytest.skip(
            f"Postgres is unreachable at {dsn!r} — start it with "
            f"`docker compose up -d postgres` ({exc})"
        )
    apply_migrations(conn)
    yield conn
    conn.close()


def _truncate_all_tables(conn: psycopg.Connection[Any]) -> None:
    """Reset every reader table between tests, keeping the migration ledger."""
    rows = conn.execute(
        "SELECT tablename FROM pg_tables"
        " WHERE schemaname = 'public' AND tablename <> 'schema_migrations'"
    ).fetchall()
    if rows:
        tables = sql.SQL(", ").join(sql.Identifier(row[0]) for row in rows)
        conn.execute(sql.SQL("TRUNCATE {} CASCADE").format(tables))
    conn.commit()


@pytest.fixture
def clean_pg(pg_conn: psycopg.Connection[Any]) -> psycopg.Connection[Any]:
    """The migrated reader database with every table truncated."""
    _truncate_all_tables(pg_conn)
    return pg_conn


@pytest.fixture
def content() -> ContentGraphRepository:
    """An in-memory Content Graph seeded with the fixture constellation."""
    repo = InMemoryContentGraphRepository()
    seed(repo)
    return repo


@pytest.fixture(params=["memory", "postgres"])
def stores(
    request: pytest.FixtureRequest,
) -> tuple[UserRepository, SessionRepository]:
    """The reader's identity + path stores — fake and real, same behaviour."""
    if request.param == "memory":
        return InMemoryUserRepository(), InMemorySessionRepository()
    conn: psycopg.Connection[Any] = request.getfixturevalue("pg_conn")
    _truncate_all_tables(conn)
    return PostgresUserRepository(conn), PostgresSessionRepository(conn)


@pytest.fixture
def users(stores: tuple[UserRepository, SessionRepository]) -> UserRepository:
    """The reader's identity store (parametrized fake / Postgres)."""
    return stores[0]


@pytest.fixture
def sessions(stores: tuple[UserRepository, SessionRepository]) -> SessionRepository:
    """The reader's durable path store (parametrized fake / Postgres)."""
    return stores[1]


@pytest.fixture
def clock() -> MutableClock:
    """A hand-advanced clock so the Session boundary is deterministic."""
    return MutableClock()


@pytest.fixture
def session_ids() -> Callable[[], str]:
    """A deterministic Session-id factory: ``session-1``, ``session-2``, ..."""
    counter = count(1)
    return lambda: f"session-{next(counter)}"


@pytest.fixture
def reader(
    content: ContentGraphRepository,
    sessions: SessionRepository,
    users: UserRepository,
    clock: MutableClock,
    session_ids: Callable[[], str],
) -> ReaderService:
    """The reader service over the seeded Content Graph and reader stores."""
    return ReaderService(content, sessions, users, clock, session_ids)


@pytest.fixture
def user_id(reader: ReaderService) -> str:
    """A registered reader identity ready to start a journey."""
    reader.create_user(USER_ID)
    return USER_ID
