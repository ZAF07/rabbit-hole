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

    Each migration runs in its own transaction and is recorded on success, so a
    re-run applies only what is pending.

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
