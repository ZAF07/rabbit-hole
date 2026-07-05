# Walking skeleton — a Piece round-trips through the ContentGraphRepository port

Status: completed
Feature: content-graph
Blocked by: none

## What to build

The walking skeleton for the whole Content Graph: a single `Piece` (title, teaser, read-time, ordered typed Content Blocks) can be written and read back through the **one** `ContentGraphRepository` port, and the exact same behavioral test passes against **both** the in-memory fake and a real Postgres running in Docker.

This slice stands up everything the other three content-graph slices build on:

- The uv-managed Python project and the `content_graph` domain package — `Piece`, `ContentBlock` as plain, framework-free types, internal vocabulary only (no branded strings — [ADR 0001](../../../docs/adr/0001-decouple-internal-and-ui-vocabulary.md)).
- The `ContentGraphRepository` port with its first two methods: `upsert_piece(piece_with_ordered_blocks)` and `get_piece(id)`.
- An **in-memory fake** implementing the port (the fast substrate the other tracks import).
- A **Postgres adapter** + the first forward migration: `pieces` (`id`, `title`, `teaser`, `read_time_min`, timestamps, **nullable `run_id`** for debug provenance only) and `blocks` (`id`, `piece_id`, `ordinal`, `kind`, `payload` JSONB). `kind ∈ {heading, paragraph, pull-quote, stat-callout, image, gif, diagram}` — the four text kinds validate/populate; the three visual kinds are **reserved but never written** in V1 ([ADR 0007](../../../docs/adr/0007-visual-provenance-sourced-or-data-grounded.md)).
- The **shared contract-test suite** parametrized over `[in-memory fake, Postgres adapter]`, with the Postgres run pointed at a docker-compose service / testcontainer so migrations and SQL are exercised, not just the fake.
- Store selection (Docker vs Supabase) read from config (`config.py` / `.env`), never hardcoded — Docker↔Supabase is a connection-config swap.

The read model returned by `get_piece` must **exclude `run_id`** and any generation-only field ([ADR 0006](../../../docs/adr/0006-generation-and-consumption-are-separate.md)).

## Acceptance criteria

- [x] A Piece with an ordered mix of the four **text** Content Block kinds round-trips: read back preserves block **order** and **kind/payload** exactly.
- [x] `upsert_piece` is **idempotent by Piece identity** — re-writing the same Piece creates no duplicate rows.
- [x] The `get_piece` read model contains **no `run_id`** (and no other generation-only field); a test asserts this.
- [x] The schema **reserves** `image`/`gif`/`diagram` block kinds; writing one is out of scope for V1 but the kind is a valid enum value (adding visuals later is a data change, not a migration).
- [x] The identical contract-test suite passes against **both** the in-memory fake **and** Postgres-in-Docker.
- [x] Store adapter is chosen by connection config; no DSN/secret is hardcoded.
- [x] Schema is created via a versioned forward **migration**.
- [x] `ruff`, `mypy`, and `pytest` all pass.

## Blocked by

- None - can start immediately

## Completion

- Completed: 2026-07-05
- Commit: `9a1f8e57077a577cf522916f54cd3ddd6138054a`
