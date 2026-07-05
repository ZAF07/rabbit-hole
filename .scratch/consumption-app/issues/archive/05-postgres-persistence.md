# Postgres persistence — real user / session / path adapters

Status: completed
Feature: consumption-app
Blocked by: 03, 04

## What to build

Make the reader's identity, Sessions, and path durable in Postgres, once the session/path/Tapestry read models are stable — reusing the **contract-test-against-Docker** pattern established in `content-graph`.

- Postgres adapters + forward migrations for the user / session / path tables backing the `UserRepository` and `SessionRepository` ports.
- The **same** behavioral suite that runs against the in-memory fakes runs against **Postgres-in-Docker**, so the two implementations can never silently diverge.
- Store selection by connection config (Docker local → Supabase scale), never hardcoded; no secrets in code.

This is the consumption side's reuse of the content-graph seam — the reader's own tables, not the shared Content Graph (which the reader only reads).

## Acceptance criteria

- [x] User / Session / path behavior passes against **both** the in-memory fakes **and** Postgres-in-Docker (one shared suite).
- [x] `PullConnection` / `Backtrack` / `ResumeSession` / `GetTapestry` all round-trip through the Postgres adapters.
- [x] Schema is created via versioned forward migrations; store selected by config; no secret hardcoded.
- [x] The reader still reads the shared Content Graph only through its read surface (these adapters are the reader's own tables).
- [x] `ruff`, `mypy`, `pytest` pass.

## Blocked by

- consumption-app/issues/03 (Session boundary + resume — the session/path shapes to persist)
- consumption-app/issues/04 (Tapestry — its read model must be stable before persisting)

## Completion

- Completed: 2026-07-05
- Commit: `46cfb47c60352c4929377ca5f4e395c1ffdfd869`
