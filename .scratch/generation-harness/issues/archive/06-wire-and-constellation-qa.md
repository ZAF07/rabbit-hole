# Wire + Constellation QA real — Weaver (hooks) + Reviewer (I1–I8, J1–J5)

Status: completed
Feature: generation-harness
Blocked by: 05

## What to build

Replace the stubbed wire + QA stages with the real **Weaver** and **Reviewer**, realizing the planned skeleton into a wired, contract-satisfying constellation.

- **Weaver** (Stage 5, once): writes every planned Connection with a **per-origin hook** — a specific curiosity gap, anti-clickbait, per-origin, in voice — realizing the `plan.md` skeleton and guaranteeing I4/I5/I6 (zero dead ends). Hooks are checked against the issue-01 `connection` evaluator.
- **Reviewer** (Stage 6, once): asserts **Tier-1 invariants I1–I8 as binary pass/fail** and judges **Tier-2 coherence J1–J5**; loops or flags. Surviving Pieces then enter the human review gate (issue 07). Produces `qa.md`.

This is the in-run mode of Weaver + Reviewer; their second (post-approval) mode lands in issue 08.

## Acceptance criteria

- [x] Every planned Connection is realized with a **passing hook** (per the `connection` evaluator); a hook identical across origins fails and is regenerated.
- [x] The wired constellation has **zero dead ends**; I4–I6 hold.
- [x] The Reviewer asserts I1–I8 binary and records J1–J5 judgements in `qa.md`; a Tier-1 failure fails the run (no soft warning on hard invariants).
- [x] Tier-2 flags are either resolved by a loop or escalated to the human queue, not silently passed.
- [x] `ruff`, `mypy`, `pytest` pass.

## Blocked by

- generation-harness/issues/05 (finalized Pieces to wire and QA)

## Completion

- Completed: 2026-07-05
- Commit: `7af81e040b8b2425c330f3f874ccc206be43fe85`
