# Human review surface — three real gates, diff-by-preservation, verdicts.jsonl

Status: completed
Feature: generation-harness
Blocked by: 06

## What to build

Make the human the real arbiter by turning the auto-approve gate hooks (issue 02) into the real **review surface**: the run's **file workspace + a runtime-agnostic verdict contract**, with **Claude Code as the V1 front-end** ([ADR 0013](../../../docs/adr/0013-human-review-surface-is-the-file-workspace.md)). The surface is _not_ a runtime feature — it's shared substrate, so review is identical under either runtime.

- **Three gates:** (1) **Plan** — Piece concepts + Connection skeleton + hook angles, after Stage 1; (2) **Piece** — each finished Piece (approve / edit-then-approve / reject-with-reason), after Stage 6, per Piece; (3) **Wired constellation** — realized hooks + graph shape, after the re-wire pass (issue 08), before the write.
- **Diff by preservation:** the machine's output is kept (`plan.machine.md`, `pieces/<id>/piece.machine.md`, `connections.machine.md`); the human edits the working copy; on approval the surface records the **unified machine→human diff** — the richest learning signal.
- **Verdict contract** — append-only `feedback/verdicts.jsonl`, one line per gate action: `ts, run_id, runtime, model, gate (plan|piece|constellation), target_id, verdict (approve|edit_approve|reject), reason, edit_diff (unified; null if none), topics[]`.

Verdicts, diffs, and the workspace **never cross the [ADR 0006](../../../docs/adr/0006-generation-and-consumption-are-separate.md) boundary** — only approved Pieces/Connections/Topics do.

## Acceptance criteria

- [x] The run **pauses** at each of the three gates and only proceeds on an approve / edit-approve verdict; a reject-with-reason is captured.
- [x] Editing the working copy then approving records a correct **unified machine→human diff** computed from the preserved `*.machine.md`.
- [x] Each gate action appends one well-formed `verdicts.jsonl` line carrying `runtime` + `model` + verdict + reason + diff + topics.
- [x] No verdict/diff/workspace field is written to the Content Graph.
- [x] `ruff`, `mypy`, `pytest` pass.

## Blocked by

- generation-harness/issues/06 (finished Pieces + wired constellation to review)

## Completion

- Completed: 2026-07-05
- Commit: `7af81e040b8b2425c330f3f874ccc206be43fe85`
