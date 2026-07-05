# Draft + Edit stages real — Writer (closed-book) + Editor (machine-QA loop)

Status: completed
Feature: generation-harness
Blocked by: 04, 01

## What to build

Replace the stubbed draft + edit stages with the real **Writer** and **Editor**, turning a vetted claim pack into a final, on-voice, grounded Piece.

- **Writer** (Stage 3, per Piece): drafts the Piece as **ordered Content Blocks** in the active **Voice Profile**, using **only** facts in the claim pack (closed-book — [ADR 0005](../../../docs/adr/0005-closed-book-grounding.md)); opens concrete, builds to the reframe, ends on a doorway. Voice is swappable by editing a Voice Profile markdown file with **no code change**.
- **Editor** (Stage 4, per Piece): tone/pacing/anti-slop edit; then the **machine-QA judge** applies the issue-01 `piece` evaluator and **loops the edit until pass or the QA budget is spent** (a bouncer, not the editor-in-chief); then **Stage 4.5 grounding check** — every factual assertion maps back to a verified claim, and drift/embellishment is cut or re-sourced.
- Output `pieces/<id>/piece.md` — the prerequisite gate for Stage 5.

## Acceptance criteria

- [x] The Writer emits well-formed ordered Content Blocks and introduces **no fact outside the claim pack** (a planted out-of-pack fact is not carried through).
- [x] The Editor's machine-QA loop **re-edits until the `piece` evaluator passes or the budget is spent**; a Piece that can't pass is flagged/escalated, never silently shipped.
- [x] The 4.5 grounding check maps every assertion to a verified claim; an embellishment with no backing claim is cut or re-sourced.
- [x] Swapping the Voice Profile file changes the house voice with **no code change** (structure/verify the seam).
- [x] `ruff`, `mypy`, `pytest` pass.

## Blocked by

- generation-harness/issues/04 (the vetted claim pack the Writer drafts from)
- generation-harness/issues/01 (the `piece` guardrail evaluator the machine-QA loop runs)

## Completion

- Completed: 2026-07-05
- Commit: `7af81e040b8b2425c330f3f874ccc206be43fe85`
