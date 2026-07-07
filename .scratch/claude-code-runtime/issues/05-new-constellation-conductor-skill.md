# 05 — The `/new-constellation` conductor skill + manual verify + doc

Status: ready-for-human
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

- [x] `.claude/skills/new-constellation/SKILL.md` exists with `/new-constellation <theme brief>` argument handling; the skill reads `manifest.toml` at run start rather than hard-coding the stage list.
- [ ] A manual `/new-constellation` run on a small Theme Brief produces a `harness/runs/<id>/` workspace with the same artifact layout as a production run, pauses at all three gates (with `*.machine.md` preservation), records verdicts via `harness verdict`, and publishes contract-valid survivors via `harness publish`. **(operator-pending — needs the web extra + a human at the gates)**
- [ ] The run's Content Graph writes go through the same write port as production; the published Pieces/Connections are readable by the reader surface, indistinguishable from DeepSeek-made ones. **(follows from the live run above; `publish` uses the same write port by construction)**
- [ ] The Stage-0 gate stops the skill on a placeholder/empty brief before any stage runs. **(construction-verified in SKILL.md; confirmed live during the operator run)**
- [x] `docs/running-a-generation-run.md` gains a `/new-constellation` section; the existing in-process-driver section points at `harness run`.
- [x] Verify evidence (the run workspace path + what was reviewed/published) is recorded in this issue's `## Comments` before it is marked done. (No automated Claude-in-CI test — validated by construction + this manual run, per ADR 0019.)

## Blocked by

- Issue 01 (`check-*`), Issue 02 (`fetch` / `verdict`), Issue 03 (`publish` / `run`), Issue 04 (live subagent tool grants).

## Comments

### 2026-07-07 — build + seam verification (agent)

**Built:**

- `.claude/skills/new-constellation/SKILL.md` — the conductor. Reads `harness/manifest.toml` + the agent cards at run start (does not hard-code the stage list), walks stages under the deliverable-on-disk prerequisite gate, fires the three human gates, and drives the deterministic seam via `uv run harness …`. Explicitly **does not** use `harness run` (that is the DeepSeek/LangGraph runtime); on this path the subagents author and the CLI only checks/records/writes. Notes the required `HARNESS_RUNTIME=claude-code` / `HARNESS_MODEL=…` stamping and the `*.machine.md` preservation the conductor owns.
- `docs/running-a-generation-run.md` — added a "Two ways to drive a run" split and a `/new-constellation` runtime section; the in-process-driver walkthrough now sits under "Driving the production engine by hand (`harness run`)".

**Seam verified from a real shell** (zero external effects — offline fixture substrate: ScriptedLLM + FakeWebSource + in-memory repo) against a real workspace at `harness/runs/verify-nc/` (populated through QA):

- `uv run harness status verify-nc` → `paused — awaiting verdict at gate: plan`, then after the plan verdict → `awaiting verdict at gate: piece p-container` (gate walk + resume works).
- `uv run harness check-constellation verify-nc` → `ok=True`, 8 invariant results (I1–I8), none failed, exit 0.
- `uv run harness check-piece verify-nc p-container` → `ok=True`, exit 0 on the clean Piece; on a slop Piece → `ok=False`, exit 1, violations `[D1 listicle scaffolding, D5 empty restating conclusion]` (fails loud, as the Editor loop requires).
- `uv run harness verdict verify-nc --gate plan --approve` after an edit to `plan.md` → recorded `edit_approve` with the machine→human diff inferred from the preserved `plan.machine.md`; stamped `runtime=claude-code`, `model=claude-opus-4-8` when `HARNESS_RUNTIME`/`HARNESS_MODEL` are exported (so the Distiller can distinguish engines — ADR 0019 §6).

**Not yet exercised live (pending infra + authorization):** the `fetch` leg needs Playwright (`uv sync --extra web` + `playwright install chromium` — not installed here), and `publish` performs real Content-Graph writes; a full `/new-constellation` run is human-in-the-loop (three interactive gates) and has external effects (live web fetches, real DB write), so it is the operator's to drive. Docker Postgres is up and `.env` has the keys; the remaining step is the web extra + a human-driven run on a small Theme Brief, then noting the published run id here. Correctness of that path rests on construction (same manifest, same specs, same shared-core `check-*`/`verdict`/`publish` seam — all verified above) per ADR 0019 §8.
