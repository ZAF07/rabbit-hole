# Topics as a multi-parent DAG + Piece tagging

Status: ready-for-agent
Feature: content-graph
Blocked by: 01

## What to build

Add the Topic taxonomy to the Content Graph as a shallow **multi-parent DAG**, and let a Piece belong to many Topics — both through the same `ContentGraphRepository` port, both proven by the shared contract-test suite against fake + Postgres.

- Migration adds `topics` (`id`, `slug`, `title`), `topic_parents(child_id, parent_id)` (a Topic may have **zero or more** parents — a strict single-parent tree is explicitly rejected, [ADR 0002](../../../docs/adr/0002-taxonomy-and-content-graph-are-separate.md)), and `piece_topics(piece_id, topic_id)` many-to-many.
- Port methods: `upsert_topic(...)`, `set_topic_parents(...)`, tag a Piece with its Topics (via `upsert_piece`'s Topic list), and `get_topics_for(piece_ids)` (each Topic with its parents) so the Tapestry can later color/cluster by Topic.
- A small **seed-taxonomy load** path that reads the V1 seed Topics from [`taxonomy.md`](../../../docs/taxonomy.md) into the store.

## Acceptance criteria

- [ ] A Topic with **several parents** round-trips — the DAG survives (not flattened to one parent).
- [ ] A Piece tagged with **several Topics** round-trips; `get_topics_for` returns each Piece's Topics with their parents.
- [ ] `upsert_topic` / `set_topic_parents` are idempotent by identity (re-running the seed load creates no duplicates).
- [ ] Seed Topics from `taxonomy.md` load into the store via the write surface.
- [ ] The Topic + tagging behaviors pass against **both** the fake and Postgres-in-Docker.
- [ ] `ruff`, `mypy`, `pytest` pass.

## Blocked by

- content-graph/issues/01 (the port, fake, Postgres adapter, and contract-test harness)
