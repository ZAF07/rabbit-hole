# Guardrail evaluators as pure functions (piece / connection / constellation)

Status: ready-for-agent
Feature: generation-harness
Blocked by: none

## What to build

*(Prefactor — no pipeline yet.)* The encoded-taste core that every later stage consumes, built first and in isolation so it is exhaustively unit-testable: the guardrail checks as **pure functions** `artifact → [violations]`, one family per guardrail spec.

- **Piece** evaluator — the anti-slop checks from [`guardrails/piece.md`](../../../harness/guardrails/piece.md), as **binary, concrete FAIL-if rules** (never "rate 1–10"): opening-on-a-definition, pure-abstraction paragraph, banned-filler phrases, etc.
- **Connection** evaluator — [`guardrails/connection.md`](../../../harness/guardrails/connection.md): shared-Topic-adjacency (not a real jump), hook-identical-from-any-origin, clickbait, etc.
- **Constellation** evaluator — [`guardrails/constellation.md`](../../../harness/guardrails/constellation.md): the **Tier-1 invariants I1–I8 as binary pass/fail** (count, required fields, Topic coverage, no dead ends, resolvable Connections, ≥1 cross-Topic per Piece, connectedness, complete grounding ledger) and the **Tier-2 coherence structure J1–J5** (Reviewer-judged).

These functions take a plain artifact (Piece / connection set / constellation) and return the specific violations. No LLM call, no I/O — deterministic and fast. They are the "highest-value unit seam" and a first-class moat artifact.

## Acceptance criteria

- [ ] Crafted fixtures assert the **specific** violation code: a Piece opening on a definition → FAIL A1; a pure-abstraction paragraph → FAIL B1; a banned-filler phrase → FAIL D3.
- [ ] A shared-Topic-adjacency Connection → FAIL A1; a hook identical from any origin → FAIL B3.
- [ ] A constellation with a dead-end → FAIL I4; a Connection to a missing Piece → FAIL I5; a Piece with no cross-Topic outbound → FAIL I6.
- [ ] Tier-1 checks return **binary** pass/fail (no numeric scores on the hard invariants).
- [ ] Evaluators are pure — same input always yields the same violation list; no network or disk.
- [ ] `ruff`, `mypy`, `pytest` pass.

## Blocked by

- None - can start immediately
