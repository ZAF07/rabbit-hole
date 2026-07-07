# Split the seven-stage god-module into per-agent deep modules

Status: completed
Feature: generation-harness
Blocked by: none

## Why

`src/harness/pipeline/stages.py` is 1279 lines — all seven pipeline actors (Architect, Researcher, Writer, Editor, Weaver, Reviewer) plus a shared kernel (workspace paths, `_fan_out`, `assemble_constellation`, the corroboration bar) share one flat namespace. Understanding one actor threads several functions interleaved with unrelated actors, and `publish.py` already reaches into the file for `piece_path` / `assemble_constellation` / `run_stage_wire`. This is a locality/AI-navigability problem, not a depth-at-the-interface one. (Architecture review candidate A, 2026-07-07.)

## What to build

Turn `stages.py` into a `stages/` package — **one deep module per agent** (agent-roster vocabulary, matching ADR 0010's Stage|Owner table) plus an explicit `_kernel` for helpers that genuinely span agents. The external interface is **unchanged**: `stages.run_stage_*` stays callable exactly as today via `stages/__init__.py` re-exports, so `graph.py`, `runtimes/manifest_runner.py`, `steps.py`, and `publish.py` keep every import line.

```
src/harness/pipeline/stages/
  __init__.py    # re-exports run_stage_* + the kernel names publish.py imports
  _kernel.py     # paths, has_failed/_record_failure, _fan_out, expanded_prerequisites,
                 #   load_brief/load_plan/voice_name, assemble_constellation
  architect.py   # run_stage_gate0, run_stage_plan (+ _assert_no_duplicates, _assert_plan_sound)
  researcher.py  # run_stage_source (+ admit_claim, _best_tier, _research_piece, _navigate_sources,
                 #   _snapshot_pages, _render_claim_pack) — the corroboration bar is sourcing-local
  writer.py      # run_stage_draft
  editor.py      # run_stage_edit (+ _qa_loop, _grounding_check, _judge, _check_guardrails_tool,
                 #   _blocks_payload, _EditResult)
  weaver.py      # run_stage_wire (+ _realize_hook)
  reviewer.py    # run_stage_qa (+ Tier-2 judging)
```

- **`_kernel`** holds only helpers used by 2+ agent modules or by `publish.py`. Agent-local helpers stay with their agent (e.g. `admit_claim`/`_best_tier` → `researcher`).
- **`publish.py`** stays the standalone ADR-0012 publish-gate orchestration; it imports `_kernel` + `weaver` instead of `stages`. No behavior change.
- **`decode.py` untouched** — colocating request/decode per agent is candidate B, a separate issue.
- No domain terms move — no `/domain-modeling` follow-up.

## Acceptance criteria

- [x] `stages.py` is replaced by a `stages/` package with one module per agent + `_kernel`; no module exceeds ~350 lines (max: editor.py at 346).
- [x] Every existing `stages.run_stage_*` and every name `publish.py` imports resolves unchanged through `stages/__init__.py` (`git diff --stat` on graph.py / manifest_runner.py / steps.py / publish.py is empty — byte-identical).
- [x] The dual-runtime parity test passes untouched — the refactor is invisible to both runtimes.
- [x] Pure re-file: no logic change. All existing tests pass without edits to their bodies.
- [x] `uv run ruff check .`, `uv run ruff format`, `uv run mypy src`, and `uv run pytest` all pass (365 passed, 1 skipped).

## Completion

- Completed: 2026-07-07
- Commit: `f2d1904b238265aa7b3abab9e3610a3340877339`
- Verified: ruff + mypy + pytest green; parity/walking-skeleton/publish-gate suites pass; zero call-site changes.

## Notes

- This is a mechanical, no-logic-change refactor; the safety net is the existing suite (end-to-end fixture run, dual-runtime parity, per-stage tests). Verify green before/after.
- Follow-ups from the same review: candidate B (give each Purpose one home — colocate request+decode), candidate C (extract the revise-until-clean loop, speculative).
