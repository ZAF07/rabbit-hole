# harness publish reports ok:true but the Content Graph write is silently rolled back

Status: completed

## Symptom

`uv run harness publish <run_id>` returns `{"ok": true, "published": [...]}` and writes `publish/published.json`, but **no rows land in Postgres** — `pieces`, `connections`, and `piece_topics` stay empty. The write is silently rolled back on process exit while the command reports success. This is silent data loss with a false success report: the operator believes the constellation published, but the reader surface sees nothing.

Observed during a real `/new-constellation invisible-systems` run: publish exited 0 twice with `published: ["the-box", "the-ledger"]`, yet `SELECT count(*) FROM pieces` returned 0 (seeded `topics` = 29 in the same DB, confirming the connection targets the right database).

Expected: after `publish` exits 0, the survivor Pieces, their Connections, and Topic tags are durably committed to the Content Graph.

## Repro

Deterministic. Minimal reproduction against the running Docker Postgres (`DATABASE_URL` set):

```python
from content_graph.config import ContentGraphConfig
from content_graph.adapters.postgres import PostgresContentGraphRepository
from content_graph.domain.piece import Piece
repo = PostgresContentGraphRepository.from_config(ContentGraphConfig.from_env())
repo.get_topic("semiconductors")          # a READ first — opens an implicit txn
repo.upsert_piece(Piece(id="diag", title="t", teaser="x", read_time_min=1,
                        blocks=(), topic_ids=("semiconductors",), run_id="diag"))
# process exits without commit  -> row is ROLLED BACK
```

A fresh connection then shows `diag` absent (0). Controlled comparison:

| Scenario                                               | Persists?                                |
| ------------------------------------------------------ | ---------------------------------------- |
| upsert **after** a preceding read, exit without commit | ❌ 0                                     |
| upsert after a read, then `repo.close()`               | ❌ 0 (`close()` rolls back in psycopg3)  |
| upsert with **no** preceding read, exit                | ✅ 1 (top-level `transaction()` commits) |
| upsert after a read, then explicit `conn.commit()`     | ✅ 1                                     |

## Root cause

Two shipped facts combine:

1. `PostgresContentGraphRepository` runs with psycopg3 **autocommit off** (`psycopg.connect(config.dsn)` in `from_config`, `src/content_graph/adapters/postgres.py:53`). Each write method uses `with self._conn.transaction(): …`. When a transaction is **already open** (because a prior SELECT started one implicitly), `conn.transaction()` opens a **nested savepoint** — releasing it does **not** commit the outer transaction.
2. `run_stage_write` performs reads (`ctx.repo.get_topic(tag)`, `src/harness/pipeline/publish.py:172`) **before** the `upsert_piece` / `upsert_connection` calls, so by the time the writes run, an implicit transaction is open and every `transaction()` block is a non-committing savepoint.
3. The CLI (`src/harness/cli.py:687-691`) opens the publish repo but its `finally` only calls the web `closer`; it never commits and never closes the repo. On process exit the outer transaction is rolled back. (Even an explicit `close()` would not help — psycopg3 `close()` rolls back an open transaction rather than committing it.)

Net: the publish write only ever survives when no read precedes it in the same connection — which is not the real code path.

## Suspected location

- `src/content_graph/adapters/postgres.py:53` — `from_config` opens the connection without `autocommit=True`.
- `src/harness/pipeline/publish.py:118-186` — `run_stage_write` reads before writing and never commits.
- `src/harness/cli.py:666-691` — publish's repo is never committed/closed.

Recommended fix: open the write connection with `autocommit=True` (`psycopg.connect(config.dsn, autocommit=True)`) so each `with conn.transaction()` block is atomic and self-committing and reads don't hold a transaction open; alternatively expose an explicit commit on the port and call it at the end of `run_stage_write` (and/or in the CLI `finally`). Verify the reader (`api`/consumption) and existing adapter tests still pass under autocommit.

## Acceptance criteria

- [x] After `uv run harness publish <run_id>` exits 0, the survivor Pieces, Connections, and Topic tags are durably present in Postgres (verified from a fresh connection).
- [x] The `run_stage_write` path (read-before-write on one connection) commits durably — a regression test asserts rows persist across a new connection.
- [x] `publish` never reports `ok: true` while rolling the write back (success ⇔ committed).
- [x] The repo's quality gates pass: `uv run ruff check .`, `uv run ruff format`, `uv run mypy src`, `uv run pytest`.

## Comments

Filed from a `/new-constellation invisible-systems` run (Claude Code generation runtime). The run's workspace under `harness/runs/invisible-systems/` is complete and contract-valid — `plan.md`, both `pieces/<id>/piece.md` (pass `check-piece`, exit 0), grounding ledgers (I8 clean), `connections.md`, `qa.md`, all three human-gate verdicts recorded, and `check-constellation` exit 0. Only the final DB persistence is affected, so once this is fixed a bare re-run of `uv run harness publish invisible-systems` will persist the exact validated survivor set with no regeneration. Diagnostic `diag%` rows were cleaned up after reproduction.

## Completion

- Completed: 2026-07-07
- Commit: `aebc53bb3171414f19ffa54ca6adb98a023a2517`
