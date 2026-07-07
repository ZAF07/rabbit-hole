"""The publish write must persist across connections, not just within its own.

Regression guard for the bug where ``PostgresContentGraphRepository.from_config``
opened the connection with autocommit OFF, so a read performed *before* the write
— exactly what ``run_stage_write`` does: ``get_topic`` before ``upsert_piece`` —
held an implicit transaction open, turning each ``with conn.transaction()`` write
into a savepoint that never committed. ``harness publish`` then reported
``ok: true`` while process exit rolled the whole write back — silent data loss.
This runs the two-connection pattern the CLI actually uses (``from_config``,
read-before-write, no explicit commit), so the fix cannot regress unnoticed.
"""

import os
from collections.abc import Iterator

import psycopg
import pytest

from content_graph.adapters.postgres import PostgresContentGraphRepository
from content_graph.config import ContentGraphConfig
from content_graph.domain.piece import Piece
from content_graph.domain.topic import Topic

_TEST_DSN = os.environ.get(
    "CONTENT_GRAPH_TEST_DSN", "postgresql://rabbit:rabbit@localhost:5433/content_graph_test"
)
_TOPIC_ID = "durability-topic"
_PIECE_ID = "durability-piece"


@pytest.fixture
def clean_rows(pg_conn: psycopg.Connection) -> Iterator[None]:
    """Drop the test's piece/topic before and after, on a committed connection.

    Depends on ``pg_conn`` so the database is migrated and the whole test is
    skipped when Postgres is unreachable, matching the contract suite.
    """

    def _cleanup() -> None:
        with psycopg.connect(_TEST_DSN, autocommit=True) as conn:
            conn.execute("DELETE FROM pieces WHERE id = %s", (_PIECE_ID,))
            conn.execute("DELETE FROM topics WHERE id = %s", (_TOPIC_ID,))

    _cleanup()
    yield
    _cleanup()


def test_publish_read_before_write_persists_across_a_fresh_connection(
    clean_rows: None,
) -> None:
    """Read-then-write on a ``from_config`` repo must be durable without an explicit commit.

    Mirrors ``run_stage_write``: a read opens the implicit transaction, the
    writes follow inside their own ``transaction()`` blocks, and the connection
    is abandoned with no commit — precisely the CLI's publish path. A fresh
    connection must then see the row; the bug left it at zero.
    """
    repo = PostgresContentGraphRepository.from_config(ContentGraphConfig(dsn=_TEST_DSN))
    assert repo.get_topic(_TOPIC_ID) is None
    repo.upsert_topic(Topic(id=_TOPIC_ID, slug=_TOPIC_ID, title="Durability"))
    repo.upsert_piece(
        Piece(
            id=_PIECE_ID,
            title="t",
            teaser="x",
            read_time_min=1,
            blocks=(),
            topic_ids=(_TOPIC_ID,),
            run_id="diag",
        )
    )
    repo.close()

    verify = psycopg.connect(_TEST_DSN, autocommit=True)
    try:
        count = verify.execute(
            "SELECT count(*) FROM pieces WHERE id = %s", (_PIECE_ID,)
        ).fetchone()[0]
    finally:
        verify.close()

    assert count == 1, "publish write was silently rolled back — not durable across connections"
