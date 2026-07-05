# The Tapestry — the reader's Personal Knowledge Graph

Status: ready-for-agent
Feature: consumption-app
Blocked by: 02

## What to build

The V1 retention asset the reader **owns**: a navigable visual node-graph of everything they've read, that visibly grows ([ADR 0009](../../../docs/adr/0009-retention-earned-not-gamified.md)).

- `GetTapestry` returns the **deduped union of the user's Session paths** — a per-user subgraph of the Content Graph: **nodes = distinct Pieces read**, **edges = Connections pulled**, colored/clustered by **Topic**.
- **Navigable:** tapping a node revisits that Piece (reread it, or pull a different thread from it) — a re-entry point, not a trophy.
- **Seeded first-run** by the reader's very first Daily Feature; **thickens every Session**.
- **Honest:** re-reading a Piece already in the trail does **not** inflate anything — the Tapestry maps distinct ground covered, not fidgeting.
- One asset, two uses: **shown** in V1; personalized-from in Phase 2 (same entity — not built here).

## Acceptance criteria

- [ ] `GetTapestry` returns the deduped union of paths: nodes = distinct Pieces read, edges = Connections pulled, clustered by Topic.
- [ ] Tapping a node resolves to its Piece as a re-entry point (reread / pull a different fork).
- [ ] The Tapestry is **seeded by the first Daily Feature** and grows across Sessions.
- [ ] Re-reading a Piece already in the trail does **not** add a duplicate node or otherwise inflate the graph.
- [ ] `ruff`, `mypy`, `pytest` pass.

## Blocked by

- consumption-app/issues/02 (the persisted Session paths the Tapestry is the union of)
