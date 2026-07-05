# Publish gate — re-wire + re-QA the approved subset, then write

Status: completed
Feature: generation-harness
Blocked by: 06, 07, content-graph/issues/01-03

## What to build

Make publishing **not a bare insert**. Because the human approves Pieces one-by-one and may reject some, the approved subset can violate the I4/I7 that QA verified over the _full_ set. The publish step therefore re-validates before writing ([ADR 0012](../../../docs/adr/0012-publish-gate-rewire-and-reqa-approved-subset.md)).

Flow: collect the approved survivors → **Weaver re-wires** them (second mode) → **Reviewer re-QAs** Tier-1 over the survivors (second mode) → a survivor that **can't** be made contract-valid is **flagged back to the human**, never published broken → the human gives the **final wired-constellation approval** (gate 3, issue 07) → **atomic write** of only the re-validated set through the `ContentGraphRepository` **write** surface.

The _published_ graph is I1–I8-valid **as shipped** — a real reader never hits a thread that goes nowhere.

## Acceptance criteria

- [x] Rejecting a Piece from the fixture constellation → the publish step re-wires + re-QAs the survivors → the **written** graph still satisfies I4/I5/I6/I7 (no dead-ends, still connected).
- [x] A survivor that can't be re-validated is **flagged, not written**.
- [x] The write is **atomic** — either the full re-validated set lands or nothing does; no partial/broken publish.
- [x] Only Pieces / Connections / Topic tags reach the graph (no generation-only field).
- [x] The final wired-constellation gate (issue 07) precedes the write.
- [x] `ruff`, `mypy`, `pytest` pass.

## Blocked by

- generation-harness/issues/06 (Weaver + Reviewer — their second/post-approval mode)
- generation-harness/issues/07 (the human verdicts that determine the approved subset)
- content-graph/issues/01-03 (the write surface for Pieces / Topics / Connections)

## Completion

- Completed: 2026-07-05
- Commit: `7af81e040b8b2425c330f3f874ccc206be43fe85`
