# apply_migrations silently drops migration DDL for any standalone caller

Status: completed

## Symptom

`content_graph.adapters.migrate.apply_migrations(conn)` returns the list of
migrations it "applied" (e.g. `['0001_pieces_and_blocks.sql', ...]`) but the
DDL does not persist for any **separate** connection. Calling it from a
standalone script (open connection → `apply_migrations` → close) leaves only the
`schema_migrations` table behind, empty; `topics`, `pieces`, `connections`,
`piece_topics` never get created.

Root cause: `apply_migrations` runs
`conn.execute("SELECT version FROM schema_migrations")` **before** the migration
loop. On a non-autocommit psycopg connection that `execute` opens a lingering
implicit transaction, so each subsequent `with conn.transaction()` in the loop
degrades to a **savepoint** rather than a top-level transaction. Releasing a
savepoint is not a commit, so when the standalone caller closes the connection
the whole implicit transaction — every migration's DDL and its
`schema_migrations` INSERT — rolls back. Only the outermost
`CREATE TABLE IF NOT EXISTS schema_migrations` survives, because it runs in its
own committed `with conn.transaction()` _before_ the stray SELECT.

Latent in the app because `src/api/main.py` keeps one long-lived connection and
reuses it for the reader repos, so it reads its own uncommitted writes. It bites
any standalone caller: a migrate CLI/one-liner, a seed script, an ops task.

Impact: a documented cold-start setup (USAGE.md) silently no-ops — the operator
believes the Content Graph is migrated when it is not; the next connection fails
with `relation "topics" does not exist`.

The same shape exists in `src/consumption/adapters/migrate.py` (identical
"SELECT already-applied, then loop with `with conn.transaction()`" structure).

## Repro

Against a fresh `content_graph` database (deterministic):

```bash
docker compose up -d postgres
docker compose exec -T postgres createdb -U rabbit content_graph 2>/dev/null || true

# Migrate via a standalone connection, then CLOSE it (no explicit commit)
uv run python -c "import os, psycopg; from dotenv import load_dotenv; from content_graph.adapters.migrate import apply_migrations; load_dotenv(); c=psycopg.connect(os.environ['CONTENT_GRAPH_DSN']); print(apply_migrations(c)); c.close()"
# -> prints all four migration names as 'applied'

# A fresh connection cannot see the tables
docker compose exec -T postgres psql -U rabbit -d content_graph -c "\dt"
# -> only `schema_migrations` (empty); no topics/pieces/connections
```

Workaround that confirms the diagnosis: adding `c.commit()` before `c.close()`
makes all four tables persist and the 29-topic taxonomy seed succeed.

## Suspected location

`src/content_graph/adapters/migrate.py` — `apply_migrations`. The stray
`conn.execute("SELECT version FROM schema_migrations").fetchall()` opens the
implicit transaction that turns the per-migration `with conn.transaction()`
blocks into savepoints. Candidate fixes: commit (or run in autocommit) around
the already-applied read, or `conn.commit()` at the end of the function so the
runner owns durability rather than the caller. Apply the same fix to
`src/consumption/adapters/migrate.py`.

## Acceptance criteria

- [x] Calling `apply_migrations` on a connection that is then closed (no caller
      commit) persists all migration DDL — a fresh connection sees the tables.
- [x] `schema_migrations` records each applied version durably, so a second
      standalone run is a no-op (idempotent across connections, not just within one).
- [x] The same fix is applied to `src/consumption/adapters/migrate.py`.
- [x] A test covers the fixed behaviour: migrate on one connection, assert the
      schema/records are visible from a **separate** connection.
- [x] Quality gates pass: `uv run ruff check .`, `uv run ruff format`,
      `uv run mypy src`, `uv run pytest`.

## Completion

- Completed: 2026-07-07
- Commit: `3c813a00604a5ec1869a12b3ed17ca3f1115ebcb`
