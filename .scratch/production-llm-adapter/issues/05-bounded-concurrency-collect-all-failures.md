# Bounded per-Piece concurrency + collect-all-failures routing into the piece gate

Status: ready-for-agent
Feature: production-llm-adapter
Blocked by: 03, 04

## Parent

PRD: `.scratch/production-llm-adapter/PRD.md` (implements [ADR 0016](../../../docs/adr/0016-production-llm-adapter-and-bounded-worker-agents.md) Decisions 6, 7).

## What to build

Make a several-hundred-call run tolerable in wall-clock time and informative in failure — without touching determinism, resume, or the learning loop.

- **Bounded per-Piece fan-out.** Source, Draft, and Edit process Pieces through a `ThreadPoolExecutor` under a **single configurable bound `N`** (a new `fan_out` knob on `HarnessConfig` with a sane default, tunable against provider rate limits without a code change). The fan-out is a **within-stage barrier** — all Pieces finish before the next stage starts — so the deliverable-on-disk gate and resume idempotence hold exactly as in the serial pipeline. A resumed run skips Pieces whose deliverable already exists; the per-Piece deliverables a concurrent run writes are **byte-identical** to a serial run's, so concurrency is an efficiency change, never a content change. (Concurrent fetching relies on slice 04's thread-local browser to bound Chromium to the pool.)
- **Collect-all-failures.** A concurrent fan-out stage no longer aborts on the first Piece to fail its bar: it lets **every** Piece finish, persists each failing artifact as the **machine copy** plus its **failure code**, and marks the failed Pieces as **piece-gate review targets** — so the human sees all the run's problems in one review pass, not one at a time across re-runs.
- **Escalate through the existing learning loop — no new machinery.** Failed Pieces route into the **piece gate** as ordinary review targets via the existing per-piece human-gate path; the human's fix is an ordinary **edit-approve Verdict** (diff-by-preservation, [ADR 0013](../../../docs/adr/0013-human-review-surface-is-the-file-workspace.md)) the Distiller already consumes ([ADR 0004](../../../docs/adr/0004-human-ratified-learning-loop.md)). An unfixable Piece becomes a **non-Survivor**, and rewire → reqa re-validate the structural invariants over the Survivors ([ADR 0012](../../../docs/adr/0012-publish-gate-rewire-and-reqa-approved-subset.md)), so dropping a bad Piece never ships a broken Content Graph. No new gate, no new Verdict kind, no new learning path.

Scope stays **within-stage, per-Piece, bounded** — no cross-stage / cross-Piece parallelism (stages still run in fixed order), and no asyncio rewrite (it's a `ThreadPoolExecutor`).

## Acceptance criteria

- [ ] Source, Draft, and Edit fan per-Piece work out through a `ThreadPoolExecutor` bounded by a configurable `fan_out` (sane default); the bound is honored.
- [ ] A fan-out run produces **byte-identical** per-Piece deliverables to a serial run.
- [ ] A resumed run skips Pieces whose deliverable already exists — concurrency never re-does completed work or breaks resume-after-pause.
- [ ] Scripting one Piece to fail its bar: the stage still finishes the others, persists the failing machine copy + failure code, and routes the failure into the piece gate as a review target.
- [ ] An edit-approve Verdict on the failed Piece + rewire/reqa yields a contract-valid Survivor set; an unfixable Piece becomes a non-Survivor and the Survivors still pass the structural invariants.
- [ ] No new gate, Verdict kind, or learning machinery is introduced — failures reuse the existing piece gate, Verdict, and Distiller substrate.
- [ ] `uv run ruff check .`, `uv run ruff format`, `uv run mypy src`, and `uv run pytest` all pass.

## Blocked by

- production-llm-adapter/issues/03 (the agentic Edit stage the fan-out wraps)
- production-llm-adapter/issues/04 (the agentic Source stage and the thread-local browser that makes concurrent fetching safe)
