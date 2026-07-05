# Connections — directed edges carrying a per-origin hook

Status: ready-for-agent
Feature: content-graph
Blocked by: 01, 02

## What to build

Make the graph traversable: directed `Connection` edges, each carrying its **own per-origin `hook`** (never a bare edge — the same destination reached from two origins can pitch two different hooks), with database-enforced referential integrity and a preview-friendly read.

- Migration adds `connections` (`id`, `from_piece_id`, `to_piece_id`, `hook`), **FK on both endpoints**, `(from_piece_id, to_piece_id)` **unique**.
- Port methods: `upsert_connection(from, to, hook)`; `get_connections_from(piece_id)` returning each Connection's `hook` **plus the destination's `title` and `topics`** in one call (so the reader can render "pull this thread" preview cards without a round-trip per card); and the ability to query a Piece's inbound + outbound Connections (so constellation-level checks and the Tapestry can be computed).
- The store **rejects** a Connection whose destination Piece does not exist — the persistence-level backstop for invariant I5 (dead links can never be stored). Note the schema *enables* checking I4/I6/I7 but does not itself guarantee them; those are generation-time invariants.

The `hook` (onward lure) lives on the edge; the Piece's `teaser` (entry lure) stays on the Piece — the two lures are never conflated.

## Acceptance criteria

- [ ] Writing a Connection then `get_connections_from` returns it with `hook` + joined destination `title` + destination `topics`.
- [ ] A Connection to a **missing destination Piece is rejected** (FK / integrity error surfaced through the port, not a silent write).
- [ ] The same destination reached from two different origins can carry **two different hooks**.
- [ ] Inbound + outbound Connections of a Piece are queryable.
- [ ] `upsert_connection` idempotent by `(from, to)` identity.
- [ ] Behaviors pass against **both** fake and Postgres-in-Docker.
- [ ] `ruff`, `mypy`, `pytest` pass.

## Blocked by

- content-graph/issues/01 (port + adapters)
- content-graph/issues/02 (Topics — the preview join returns destination Topics)
