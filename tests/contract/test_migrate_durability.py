"""Migrations must persist across connections, not just within the one that ran them.

Regression guard for the bug where ``apply_migrations`` left a stray
``SELECT`` open before the migration loop, turning each per-migration
``with conn.transaction()`` into a savepoint that never committed. A standalone
caller — migrate, close the connection, done — then silently lost every table:
the app only ever worked because it reused one long-lived connection and read
its own uncommitted writes. These tests run the two-connection pattern a real
operator uses, so the fix cannot regress unnoticed.
"""

import os
from collections.abc import Callable, Iterator
from typing import Any

import psycopg
import pytest
from psycopg import sql

from consumption.adapters import migrate as consumption_migrate
from content_graph.adapters import migrate as content_graph_migrate

MigrateFn = Callable[[psycopg.Connection[Any]], list[str]]

_RUNNERS = {
    "content_graph": (content_graph_migrate.apply_migrations, "content_graph_migrate_test"),
    "consumption": (consumption_migrate.apply_migrations, "consumption_migrate_test"),
}


def _admin_dsn() -> str:
    """The Postgres server DSN (``postgres`` db) the docker-compose service exposes."""
    base = os.environ.get(
        "CONTENT_GRAPH_TEST_DSN", "postgresql://rabbit:rabbit@localhost:5433/content_graph_test"
    )
    return psycopg.conninfo.make_conninfo(base, dbname="postgres")


def _reset_database(admin_dsn: str, dbname: str) -> None:
    """Drop and recreate a throwaway database so each run starts from bare Postgres."""
    drop = sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(dbname))
    create = sql.SQL("CREATE DATABASE {}").format(sql.Identifier(dbname))
    with psycopg.connect(admin_dsn, autocommit=True) as conn:
        conn.execute(drop)
        conn.execute(create)


@pytest.fixture(params=sorted(_RUNNERS))
def fresh_db(request: pytest.FixtureRequest) -> Iterator[tuple[MigrateFn, str]]:
    """Yield a runner and the DSN of a freshly created, un-migrated database.

    Skips the whole test when Postgres is unreachable, matching the contract
    suite's behaviour, and drops the throwaway database on the way out.
    """
    migrate_fn, dbname = _RUNNERS[request.param]
    admin_dsn = _admin_dsn()
    try:
        _reset_database(admin_dsn, dbname)
    except psycopg.OperationalError as exc:
        pytest.skip(
            f"Postgres is unreachable at {admin_dsn!r} — start it with "
            f"`docker compose up -d postgres` ({exc})"
        )
    dsn = psycopg.conninfo.make_conninfo(admin_dsn, dbname=dbname)
    try:
        yield migrate_fn, dsn
    finally:
        with psycopg.connect(admin_dsn, autocommit=True) as conn:
            conn.execute(
                sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(dbname))
            )


def test_migrations_visible_from_a_separate_connection(
    fresh_db: tuple[MigrateFn, str],
) -> None:
    """Apply migrations on one connection, then read the schema back on another.

    The applying connection is closed with no explicit commit — exactly what a
    standalone migrate script does — so a durable runner must have committed the
    DDL itself. A fresh connection must see the migrated tables and the full
    recorded ledger; the bug left only an empty ``schema_migrations`` behind.
    """
    migrate_fn, dsn = fresh_db

    applier = psycopg.connect(dsn)
    applied = migrate_fn(applier)
    applier.close()

    assert applied, "the runner reported no migrations applied against a bare database"

    reader = psycopg.connect(dsn)
    try:
        recorded = {
            row[0] for row in reader.execute("SELECT version FROM schema_migrations").fetchall()
        }
        assert recorded == set(applied), (
            "the migration ledger did not persist for a separate connection: "
            f"applied {sorted(applied)}, but another connection sees {sorted(recorded)}"
        )
        tables = {
            row[0]
            for row in reader.execute(
                "SELECT tablename FROM pg_tables"
                " WHERE schemaname = 'public' AND tablename <> 'schema_migrations'"
            ).fetchall()
        }
        assert tables, "no migrated tables are visible from a separate connection"
    finally:
        reader.close()


def test_re_running_on_a_fresh_connection_is_a_no_op(
    fresh_db: tuple[MigrateFn, str],
) -> None:
    """A second standalone run sees the first run's work and applies nothing.

    Idempotence has to hold *across* connections, not merely within the one that
    first ran the migrations — the property the savepoint bug quietly broke.
    """
    migrate_fn, dsn = fresh_db

    first = psycopg.connect(dsn)
    migrate_fn(first)
    first.close()

    second = psycopg.connect(dsn)
    try:
        reapplied = migrate_fn(second)
        assert reapplied == [], "migrations re-applied against an already-migrated database"
    finally:
        second.close()
