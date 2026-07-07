"""Forward-only, versioned migration runner for the reader's store.

Mirrors the Content Graph's runner but reads the consumption subsystem's own
migrations — each subsystem owns and applies its own half of the schema.
"""

from importlib import resources
from typing import Any

import psycopg

_MIGRATIONS_PACKAGE = "consumption.adapters.migrations"


def load_migrations() -> list[tuple[str, str]]:
    """Load every packaged migration in version (filename) order.

    Returns:
        Pairs of (version name, SQL text), sorted ascending by version.
    """
    package = resources.files(_MIGRATIONS_PACKAGE)
    names = sorted(entry.name for entry in package.iterdir() if entry.name.endswith(".sql"))
    return [(name, (package / name).read_text(encoding="utf-8")) for name in names]


def apply_migrations(conn: psycopg.Connection[Any]) -> list[str]:
    """Apply every migration not yet recorded in ``schema_migrations``.

    Each migration runs in its own top-level transaction and is committed on
    success, so the work persists for any later connection and a re-run applies
    only what is pending. The already-applied read stays inside the ledger's
    own transaction: left outside, it would open a dangling transaction that
    demotes every per-migration ``transaction()`` to an uncommitted savepoint,
    silently discarding the DDL when a standalone caller closes the connection.

    Args:
        conn: An open connection to the target database.

    Returns:
        The version names applied by this call, in order.
    """
    with conn.transaction():
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            " version TEXT PRIMARY KEY,"
            " applied_at TIMESTAMPTZ NOT NULL DEFAULT now())"
        )
        already_applied = {
            row[0] for row in conn.execute("SELECT version FROM schema_migrations").fetchall()
        }
    applied_now: list[str] = []
    for version, sql_text in load_migrations():
        if version in already_applied:
            continue
        with conn.transaction():
            conn.execute(sql_text)
            conn.execute("INSERT INTO schema_migrations (version) VALUES (%s)", (version,))
        applied_now.append(version)
    return applied_now
