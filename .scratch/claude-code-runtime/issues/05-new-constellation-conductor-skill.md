# 05 — The `/new-constellation` conductor skill + manual verify + doc

Status: ready-for-agent
Feature: claude-code-runtime

## Parent

PRD: [.scratch/claude-code-runtime/PRD.md](../PRD.md) · [ADR 0019](../../../docs/adr/0019-claude-code-generation-runtime-and-shared-harness-cli.md)

## What to build

The conductor that makes Claude Code a second real runtime: a `.claude/skills/new-constellation/SKILL.md` invoked as `/new-constellation <theme brief>`. It is a **conductor persona, not a restatement of the pipeline**. It instructs Claude Code to:

1. Run the **Stage-0 gate** (Editorial DNA + Theme Brief present, no placeholders) and stop loud on failure.
2. Read `harness/manifest.toml` + the agent cards at run start, and walk stages in **manifest order**, enforcing the deliverable-on-disk prerequisite gate (a stage cannot start until its inputs exist; re-invoking resumes from the first missing artifact).
3. Delegate each stage to its subagent (Architect → Researcher → Writer → Editor → Weaver → Reviewer), with the Researcher grounding via `harness fetch`, the Editor revising against `harness check-piece`, and the Reviewer's Tier-1 asserted via `harness check-constellation`.
4. At each of the three human gates (plan → each Piece → wired constellation), present the artifact + the relevant `harness check-*` report, take the human's decision in-session, record it via `harness verdict`, and resume.
5. Publish via `harness publish`.

Claude does the creative/judgment work; the seam enforces the binary contract and does the write — parity by construction. No new orchestrator agent card (the skill body is the conductor). Then do a **manual verify run** and add a `/new-constellation` section to `docs/running-a-generation-run.md`.

## Acceptance criteria

- [ ] `.claude/skills/new-constellation/SKILL.md` exists with `/new-constellation <theme brief>` argument handling; the skill reads `manifest.toml` at run start rather than hard-coding the stage list.
- [ ] A manual `/new-constellation` run on a small Theme Brief produces a `harness/runs/<id>/` workspace with the same artifact layout as a production run, pauses at all three gates (with `*.machine.md` preservation), records verdicts via `harness verdict`, and publishes contract-valid survivors via `harness publish`.
- [ ] The run's Content Graph writes go through the same write port as production; the published Pieces/Connections are readable by the reader surface, indistinguishable from DeepSeek-made ones.
- [ ] The Stage-0 gate stops the skill on a placeholder/empty brief before any stage runs.
- [ ] `docs/running-a-generation-run.md` gains a `/new-constellation` section; the existing in-process-driver section points at `harness run`.
- [ ] Verify evidence (the run workspace path + what was reviewed/published) is recorded in this issue's `## Comments` before it is marked done. (No automated Claude-in-CI test — validated by construction + this manual run, per ADR 0019.)

## Blocked by

- Issue 01 (`check-*`), Issue 02 (`fetch` / `verdict`), Issue 03 (`publish` / `run`), Issue 04 (live subagent tool grants).
