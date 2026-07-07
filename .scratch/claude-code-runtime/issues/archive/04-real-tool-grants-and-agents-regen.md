# 04 — Real tool grants + `.claude/agents/` regen

Status: completed
Feature: claude-code-runtime

## Parent

PRD: [.scratch/claude-code-runtime/PRD.md](../PRD.md) · [ADR 0019](../../../docs/adr/0019-claude-code-generation-runtime-and-shared-harness-cli.md)

## What to build

Make the subagent cards actually runnable under Claude Code by replacing their placeholder tool grants with real ones pointing at the `harness` CLI.

In `harness/agents/README.md`, change the `tools:` frontmatter on the cards whose subagents call the seam — **Researcher** (calls `harness fetch`), **Editor** (calls `harness check-piece`), **Reviewer** (calls `harness check-constellation`) — from the `WebSourcePort` placeholder to a real **`Bash`** grant scoped to the `harness` CLI. Regenerate `.claude/agents/` from that single source of truth, and extend the existing agent-card drift test to expect the new grants so the cards and generated subagents can never drift.

This is a spec/regeneration slice: no CLI logic changes. It depends on the commands the grants reference already existing.

## Acceptance criteria

- [x] The Researcher / Editor / Reviewer cards in `harness/agents/README.md` grant `Bash` (scoped to `harness`) instead of the `WebSourcePort` placeholder; the other cards are unchanged.
- [x] `.claude/agents/` is regenerated so `researcher.md` / `editor.md` / `reviewer.md` reflect the new grants.
- [x] The agent-card drift test (`tests/harness/test_agent_cards.py`) asserts the new grants and passes; no parallel test is added.
- [x] No occurrence of the non-tool `WebSourcePort` grant remains in the cards.
- [x] `ruff`, `mypy src`, `pytest` pass.

## Blocked by

- Issue 01 (`check-piece` / `check-constellation` exist).
- Issue 02 (`fetch` exists).

## Completion

- Completed: 2026-07-07
- Commit: <to be filled in manually>
