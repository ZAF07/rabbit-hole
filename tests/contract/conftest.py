"""The one seam: every contract test runs against both port implementations.

The ``repo`` fixture is parametrized over the in-memory fake and the Postgres
adapter (pointed at the docker-compose service), so the fake the other tracks
build on and the real SQL can never silently diverge.
"""

import os
from collections.abc import Iterator
from typing import Any

import psycopg
import pytest
from psycopg import sql

from content_graph.adapters.memory import InMemoryContentGraphRepository
from content_graph.adapters.migrate import apply_migrations
from content_graph.adapters.postgres import PostgresContentGraphRepository
from content_graph.ports.repository import ContentGraphRepository

TEST_DSN_ENV_VAR = "CONTENT_GRAPH_TEST_DSN"
DEFAULT_TEST_DSN = "postgresql://rabbit:rabbit@localhost:5433/content_graph_test"


def _test_dsn() -> str:
    return os.environ.get(TEST_DSN_ENV_VAR, DEFAULT_TEST_DSN)


def _ensure_test_database(dsn: str) -> None:
    """Create the test database if it does not exist yet."""
    params = psycopg.conninfo.conninfo_to_dict(dsn)
    dbname = str(params.get("dbname", ""))
    admin_dsn = psycopg.conninfo.make_conninfo(dsn, dbname="postgres")
    with psycopg.connect(admin_dsn, autocommit=True) as conn:
        exists = conn.execute("SELECT 1 FROM pg_database WHERE datname = %s", (dbname,)).fetchone()
        if not exists:
            conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(dbname)))


@pytest.fixture(scope="session")
def pg_conn() -> Iterator[psycopg.Connection[Any]]:
    """Session connection to the migrated Postgres test database."""
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
    """Reset every content table between tests, keeping the migration ledger."""
    rows = conn.execute(
        "SELECT tablename FROM pg_tables"
        " WHERE schemaname = 'public' AND tablename <> 'schema_migrations'"
    ).fetchall()
    if rows:
        tables = sql.SQL(", ").join(sql.Identifier(row[0]) for row in rows)
        conn.execute(sql.SQL("TRUNCATE {} CASCADE").format(tables))
    conn.commit()


@pytest.fixture(params=["memory", "postgres"])
def repo(request: pytest.FixtureRequest) -> ContentGraphRepository:
    """The ContentGraphRepository under test — fake and real, same behavior."""
    if request.param == "memory":
        return InMemoryContentGraphRepository()
    conn: psycopg.Connection[Any] = request.getfixturevalue("pg_conn")
    _truncate_all_tables(conn)
    return PostgresContentGraphRepository(conn)
