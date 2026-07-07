# 02 — `harness fetch` + `harness verdict`

Status: completed
Feature: claude-code-runtime

## Parent

PRD: [.scratch/claude-code-runtime/PRD.md](../PRD.md) · [ADR 0019](../../../docs/adr/0019-claude-code-generation-runtime-and-shared-harness-cli.md)

## What to build

The two seam commands the Researcher subagent and the human gates depend on, added to the CLI from issue 01.

- `harness fetch <url>` — call the Playwright `WebSourcePort.fetch` and print the fetched page as JSON (`{url, content, outlinks, fetched_at}`), or a null/again signal on navigation failure. This is the recall-first, no-search-engine grounding primitive ([ADR 0011](../../../docs/adr/0011-harness-tools-are-ports-web-sourcing-recall-first.md)): the Researcher recalls candidate URLs itself, then fetches + citation-chases by following the returned `outlinks`. Raw text + outlinks are returned so closed-book fidelity holds — no summarization.
- `harness verdict <run_id> --gate <plan|piece|constellation> [--target <piece_id>] (--approve | --reject --reason "…")` — resolve the manifest's `HumanGateSpec`, call `record_verdict` against the run workspace, and append to `feedback/verdicts.jsonl`. `edit_approve` is **inferred** from the machine→human diff (never passed); a reject requires a reason. Reuses the [ADR 0013](../../../docs/adr/0013-human-review-surface-is-the-file-workspace.md) contract unchanged — this command is only a new front-end onto it.

## Acceptance criteria

- [x] `harness fetch <url>` over the `fixture_web_source` returns the canned page's content + outlinks as JSON and exits 0; a URL with no page returns the null/again signal and a non-zero (or clearly-flagged) exit.
- [x] `harness verdict … --approve` appends a record such that `WorkspaceVerdictGates` then reads the target as approved; `--reject` without `--reason` errors; `--reject --reason` records the reason.
- [x] Approving a working copy that was **edited** away from its `*.machine.md` is recorded as `edit_approve` with the unified diff attached; approving an unedited copy is recorded as `approve`.
- [x] The per-piece gate requires `--target`; the plan/constellation gates use the gate name as target.
- [x] `tests/harness/test_cli.py` covers both commands over the `fixture_run` substrate (fake web source; workspace verdict round-trip), asserting exit code + stdout + `verdicts.jsonl` / gate-decision side-effects.
- [x] `ruff`, `mypy src`, `pytest` all pass.

## Blocked by

- Issue 01 (the CLI core, dispatch, and test harness).

## Completion

- Completed: 2026-07-07
- Commit: <to be filled in manually>
