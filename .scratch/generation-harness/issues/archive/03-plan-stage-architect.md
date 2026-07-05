# Plan stage real — the Architect designs the constellation (the moat)

Status: completed
Feature: generation-harness
Blocked by: 02

## What to build

Replace the stubbed plan stage with the real **Architect** — the plan-first designer where the moat lives. Given a Theme Brief, it designs the **entire constellation before any prose is written**: every Piece concept (title + premise + Topic tags) and the full Connection skeleton (each origin→destination with its intended hook angle), such that the structural invariants hold **by construction**.

- Reads the **Editorial DNA**, the Theme Brief (`goal.md`), the taxonomy, `connection.md` + `constellation.md`, and the existing Content Graph **via the `ContentGraphRepository` read port** to bridge to prior Pieces and avoid duplicating them.
- Designs the Connection graph so I6 (≥1 cross-Topic per Piece), I4 (no dead ends), and I7 (connected) are satisfiable by construction; marks entry-worthy nodes (J3) that can open cold as a Daily Feature.
- **Stage-0 gate** made real: a Brief with any unfilled `<placeholder>` fails the gate (per [`harness/briefs/TEMPLATE.md`](../../../harness/briefs/TEMPLATE.md)).
- Produces `plan.md` (no placeholders); this is the prerequisite gate for Stage 2.

## Acceptance criteria

- [x] Given a fixture Brief (through-line + target Topics + piece-count), the Architect emits a `plan.md` with Piece concepts + full Connection skeleton spanning the Brief's target Topics.
- [x] The planned skeleton is structurally sound: no dead ends, ≥1 cross-Topic edge per Piece, connected (checked with the constellation evaluator over the plan).
- [x] Entry-worthy nodes (J3) are marked.
- [x] The Architect calls the ContentGraph **read** surface and does not propose a Piece that duplicates an existing one in a seeded graph.
- [x] A Brief with an unfilled placeholder **fails Stage 0** before the Architect runs.
- [x] `ruff`, `mypy`, `pytest` pass.

## Blocked by

- generation-harness/issues/02 (the gated StateGraph, ports, run workspace)

## Completion

- Completed: 2026-07-05
- Commit: `7af81e040b8b2425c330f3f874ccc206be43fe85`
