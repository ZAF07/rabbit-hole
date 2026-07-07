# PRD: The Claude Code generation runtime & the shared `harness` CLI seam

Status: ready-for-agent
Feature: claude-code-runtime
Depends on: `generation-harness` (the gated pipeline, the manifest runner, the guardrail evaluators, the three human gates, the review surface, the Distiller — all shipped) and `production-llm-adapter` (the DeepSeek adapter, the `WebSourcePort` Playwright adapter, bounded fan-out — all shipped)

> This PRD implements [ADR 0019](../../docs/adr/0019-claude-code-generation-runtime-and-shared-harness-cli.md): the interactive **Claude Code runtime** for content generation, triggered by a `/new-constellation` skill, held to the same outcome contract as the production DeepSeek/LangGraph path by a new first-class **`harness` CLI** that is the shared deterministic core both the human driver and the Claude subagents call. It stays **generation-only** — nothing here crosses into consumption ([ADR 0006](../../docs/adr/0006-generation-and-consumption-are-separate.md)) — and it does **not** reopen the pipeline's *shape* ([ADR 0010](../../docs/adr/0010-content-generation-pipeline-architecture.md)): plan-first, the outcome contract, the three human gates, and determinism-by-construction all hold. It *fills in* ADR 0010's long-declared second runtime, which until now had subagent cards but no conductor.

## Problem Statement

The generation harness can only be run one way: the production **DeepSeek + LangGraph** engine, triggered over HTTP (`POST /admin/generation/runs`) or driven in-process by a scratch script. [ADR 0010](../../docs/adr/0010-content-generation-pipeline-architecture.md) promised a **second, interactive runtime** — Claude Code as the engine, for authoring, iterating, and walking the human-review gates — but only its raw materials exist:

- The **seven subagent cards** are generated into `.claude/agents/`, but there is **no conductor** — no skill that runs a full gated constellation by walking the pipeline and delegating to them.
- Those cards' tool grants are **placeholders**: `researcher.md` declares `tools: WebSourcePort`, which is not a real Claude Code tool, so the Researcher could not fetch or ground even if invoked.
- There is no way for a human to trigger, drive, and human-approve a full generation run **from inside Claude Code**, matching the way `~/we-os` exposes its pipeline through both an HTTP trigger and a `/new-campaign` skill.

So today the "same run, two runtimes" guarantee is unrealized: the interactive path a human would use to *author with a strong model and review as they go* does not exist, and there is no shared, tested seam that would let a Claude-driven run be held to the **same binary Tier-1 contract** and the **same atomic Content Graph write** the production path guarantees.

## Solution

A **`/new-constellation <theme brief>`** Claude Code skill that runs the full gated pipeline **interactively** — Claude Code is the conductor and the engine, delegating each stage to the seven subagents — producing the *same* run workspace (`harness/runs/<id>/`), pausing at the *same* three human gates (plan → each Piece → wired constellation), and publishing the *same* contract-valid constellation as the production path. The reader never learns which engine made a Piece.

Underneath, a new first-class **`harness` CLI** (`src/harness/cli.py`, a console script) is the **shared deterministic core** both the human and the subagents invoke via `Bash`:

- `harness check-piece <run> <piece_id>` / `harness check-constellation <run>` — run the existing `evaluate_piece` / `evaluate_constellation` / `evaluate_connections` functions and report the binary **Tier-1 invariants (I1–I8)**, anti-slop phrase bans, and grounding-ledger validity.
- `harness fetch <url>` — the Playwright `WebSourcePort` recall-first fetch + citation-chase (raw text + outlinks), honoring [ADR 0011](../../docs/adr/0011-harness-tools-are-ports-web-sourcing-recall-first.md).
- `harness verdict <run> --gate <g> [--target <piece_id>] (--approve | --reject --reason …)` — append to the shared `feedback/verdicts.jsonl` via the existing `record_verdict`.
- `harness publish <run>` — the post-approval rewire → reqa → **atomic Content Graph write** over the approved survivors ([ADR 0012](../../docs/adr/0012-publish-gate-rewire-and-reqa-approved-subset.md)).
- `harness run <run> [--brief …]` / `harness status <run>` — start/resume an in-process run (production engine) and report where it paused; folds in the throwaway `scripts/gen.py` driver.

Because every binary contract check and the DB write are **one shared implementation both engines are forced through**, "the same run via Claude Code" becomes a *property*, not a hope: Claude does the creative and judgment work; the seam disposes.

## User Stories

1. As an operator, I want to trigger a full generation run from inside Claude Code by typing `/new-constellation <theme brief>`, so that I can author a constellation interactively with Claude as the engine instead of only via the DeepSeek HTTP trigger.
2. As an operator, I want the skill to run the Stage-0 gate first (Editorial DNA + Theme Brief present, no placeholders), so that a thin or malformed brief fails loud before any stage runs.
3. As an operator, I want the skill to read `harness/manifest.toml` at run start and walk the stages in manifest order, so that the pipeline is defined in exactly one place and editing the manifest changes both runtimes.
4. As an operator, I want the conductor to honor the deliverable-on-disk prerequisite gate, so that a stage never starts until its inputs exist and re-invoking resumes from the first missing artifact.
5. As an operator, I want the Architect subagent to produce `plan.md` (Piece concepts + Connection skeleton) designed so the Tier-1 invariants hold by construction, so that the plan is a valid foundation before any Piece is written.
6. As an operator, I want the run to pause at the **plan gate** and show me `plan.md`, so that I can approve, edit-then-approve, or reject it with a reason before sourcing begins.
7. As an operator, I want the Researcher subagent to ground closed-book by recalling candidate URLs and calling `harness fetch` to fetch and citation-chase, so that the claim pack and `grounding.json` are produced by the same `WebSourcePort` discipline as production (recall-first, no search engine).
8. As an operator, I want a thin source pack to fail loud and early (before the Writer runs), so that a Piece dies at research rather than being papered over in prose.
9. As an operator, I want the Writer subagent to draft only from the vetted claim pack, so that every factual assertion is traceable and closed-book grounding holds.
10. As an operator, I want the Editor subagent to revise against `harness check-piece` until it passes or the QA budget is spent, so that the anti-slop and grounding contract is enforced by the same deterministic checker both runtimes use.
11. As an operator, I want the Weaver subagent to write per-origin hooks and realize the planned Connections, so that every Connection has a passing hook and there are zero dead ends.
12. As an operator, I want the Reviewer subagent to judge Tier-2 coherence while `harness check-constellation` asserts the binary Tier-1 invariants, so that structural correctness is machine-decided and only taste is model-judged.
13. As an operator, I want the run to pause at the **per-Piece gate** and show me each `pieces/<id>/piece.md` with its guardrail report, so that I can approve, edit-approve, or reject each Piece one at a time (V1).
14. As an operator, I want my in-session decision recorded to `feedback/verdicts.jsonl` via `harness verdict`, so that the Distiller learns from Claude-runtime verdicts exactly as it does from production ones.
15. As an operator, I want an edited-then-approved artifact recorded as `edit_approve` with the machine→human diff, so that my edits become the richest learning signal without my having to say so.
16. As an operator, I want `harness publish` to re-wire and re-QA the approved survivors and then atomically write only the re-validated set, so that rejecting some Pieces never leaves the graph in a broken state.
17. As an operator, I want the run to pause at the **constellation gate** and show me `publish/connections.md`, so that I give a final wired-constellation approval before the write.
18. As an operator, I want the final write to go through the same `ContentGraphRepository` write port as production, so that a Claude-made constellation is indistinguishable to the reader from a DeepSeek-made one.
19. As an operator, I want to run any single seam command by hand (`harness check-piece …`, `harness fetch …`, `harness verdict …`, `harness publish …`), so that I can inspect or drive one step without the whole skill.
20. As an operator, I want the human in-process driver (`harness run` / `harness status`) folded into the same CLI, so that there is one supported tool instead of a scratch script.
21. As an operator, I want the seam commands to exit non-zero and print a structured report on failure, so that both I and the subagents can branch on the result.
22. As a maintainer, I want the researcher/editor/reviewer cards' tool grants replaced with real `Bash`-scoped grants to the `harness` CLI, so that the subagents can actually call the seam and the placeholder `WebSourcePort` grant is gone.
23. As a maintainer, I want the tool-grant change regenerated into `.claude/agents/` and guarded by the existing drift test, so that the cards and generated subagents never drift.
24. As a maintainer, I want the CLI's contract enforcement and DB write to be the *same code* the production runtime uses, so that the two runtimes cannot silently disagree about what passes or what gets written.
25. As a maintainer, I want the automated parity test to stay on the two Python runtimes and the Claude runtime validated by construction, so that I get parity assurance without running Claude in CI.
26. As an operator, I want a run's workspace to be interoperable between engines (same artifact layout, same `*.machine.md` preservation, same verdict log), so that a run could in principle be resumed across engines even though I normally keep one run on one engine.
27. As a maintainer, I want `harness` wired from environment config in `main()` exactly as `api/main.py` wires the app, so that production adapters (Postgres, DeepSeek, Playwright) are selected the same way and secrets stay in `config.py`/`.env`.
28. As an operator, I want the operator walkthrough doc to grow a `/new-constellation` section, so that the interactive runtime is documented alongside the in-process driver.

## Implementation Decisions

- **New module: the `harness` CLI (`src/harness/cli.py`), a console script.** Registered in `pyproject.toml` (e.g. `harness = "harness.cli:main"`). Subcommands: `check-piece`, `check-constellation`, `fetch`, `verdict`, `publish`, `run`, `status`. It is the *only* new production module of substance; everything else is spec/markdown or thin edits.
- **The CLI is split into a testable core and an env-wiring `main`.** A `run_cli(argv, *, ports…)`-style core executes each subcommand over **injected** ports/workspace/specs and returns an exit code + writes structured stdout; a thin `main()` resolves the real adapters from environment (mirroring `build_app_from_env` in `api/main.py`) and delegates to the core. Only the core is unit-tested. This is the single seam.
- **Each subcommand is a thin adapter over already-shipped functions**, not new logic:
  - `check-piece` / `check-constellation` → `evaluate_piece` / `evaluate_constellation` / `evaluate_connections` (+ banned phrases from `SpecLibrary`), emitting the violation list as JSON and a non-zero exit on any violation.
  - `fetch` → `WebSourcePort.fetch`, emitting `{content, outlinks, fetched_at}` (or a null/again signal on navigation failure), so the Researcher subagent can recall-then-fetch and citation-chase.
  - `verdict` → `record_verdict` against the run workspace + the manifest's `HumanGateSpec`; `edit_approve` is inferred from the machine→human diff, never passed.
  - `publish` → the existing rewire → reqa → write steps (`steps.rewire_update` / `reqa_update` / `write_update` or their extraction), writing only the re-validated survivor set through the `ContentGraphRepository` write port.
  - `run` / `status` → build a `RunContext` and call `run_pipeline` (production engine), reporting the paused gate; **folds in and then deletes `scripts/gen.py`**.
- **The `/new-constellation` skill is a conductor persona, not a re-statement of the pipeline.** `.claude/skills/new-constellation/SKILL.md` instructs Claude Code to: (1) run the Stage-0 gate; (2) read `harness/manifest.toml` + the agent cards at run start; (3) walk stages in manifest order, enforcing the deliverable-on-disk prerequisite gate; (4) delegate each stage to its subagent; (5) at each human gate, present the artifact + the relevant `harness check-*` report, take the human's decision, record it via `harness verdict`, and resume. No new orchestrator subagent card — the skill body is the conductor.
- **Subagent creative work is Claude; the binary contract and the write are the seam.** Architect, Researcher (recall + drive `fetch`), Writer, Editor (prose/anti-slop revision), Weaver (hooks), and Reviewer (Tier-2 coherence) run as Claude subagents; every Tier-1 invariant, ledger validation, verdict record, and the DB write are the shared Python called through the CLI. This is the "propose vs dispose" split of [ADR 0016](../../docs/adr/0016-production-llm-adapter-and-bounded-worker-agents.md) decision 3, lifted from inside-a-stage to across-the-runtime.
- **Tool grants become real.** In `harness/agents/README.md`, the researcher/editor/reviewer cards' `tools:` frontmatter changes from the `WebSourcePort` placeholder to a real `Bash` grant scoped to the `harness` CLI; `.claude/agents/` is regenerated from that file.
- **Human gates reuse the shared verdict contract unchanged** ([ADR 0013](../../docs/adr/0013-human-review-surface-is-the-file-workspace.md)): `preserve_and_decide`, `*.machine.md` preservation, `WorkspaceVerdictGates`, and `feedback/verdicts.jsonl` are identical; the CLI's `verdict` command is the only new front-end onto them. The `model` field on a verdict distinguishes the Claude engine from DeepSeek.
- **No pipeline-shape change.** The manifest, stage order, gate points, guardrail evaluators, publish steps, and the Content Graph write are untouched; this feature adds a conductor + a CLI over them.
- **Environment/config parity.** `main()` reads the same `LLMConfig`, `ContentGraphConfig`, `HARNESS_ROOT`, and `HARNESS_FAN_OUT` knobs the API uses; no new secret surface.

## Testing Decisions

- **What a good test asserts here: the CLI contract, not the underlying logic.** Each subcommand's test drives `run_cli(argv, …)` in-process with injected fakes and asserts only externally observable behavior — **exit code**, **stdout (structured JSON)**, and **side-effects on the run workspace / in-memory repo**. It does *not* re-assert what `evaluate_piece`, `record_verdict`, or the publish steps already guarantee (those have their own tests); a CLI test that duplicates guardrail assertions is testing the wrong layer.
- **One new test module (the single seam):** `tests/harness/test_cli.py`, exercising all subcommands over the shared offline substrate in [`tests/harness/fixture_run.py`](../../tests/harness/fixture_run.py) — `build_context(tmp_path, …)` with `well_behaved_llm()`, `fixture_web_source()`, `InMemoryContentGraphRepository`, `AutoApproveGates`. Representative cases: `check-piece` clean → exit 0 + empty violations; `check-piece` on a doctored slop draft → non-zero + the expected violation codes; `fetch` a fixture hub URL → its canned content + outlinks; `verdict --approve` → a record appended and the gate reads approved; `verdict` on an edited working copy → `edit_approve` with a diff; `publish` over an approved fixture run → the survivor set written to the in-memory repo.
- **Reused existing seam — the agent-card drift test** ([`tests/harness/test_agent_cards.py`](../../tests/harness/test_agent_cards.py)) covers the tool-grant change and `.claude/agents/` regeneration; extend its expectations to the new `Bash` grants rather than adding a parallel test.
- **No automated test for the `SKILL.md` prose.** The conductor is validated *by construction* (it walks the manifest and is forced through the seam's gates and write) plus a manual `/new-constellation` run; this matches how the repo already treats the Claude Code runtime, with the [dual-runtime parity test](../../tests/harness/pipeline/test_dual_runtime_parity.py) staying on the Python engines.
- **Prior art to mirror:** `test_review_surface.py` (verdict/gate behavior over a workspace), `test_publish_gate.py` (rewire/reqa/write over survivors), and the `fixture_run` fakes used throughout `tests/harness/pipeline/`.
- **Quality gates unchanged:** `ruff check`, `ruff format`, `mypy src`, `pytest` all green; the CLI core is type-annotated and mypy-clean like the rest of `src/harness/`.

## Out of Scope

- **Any change to the pipeline's shape** — stages, gate points, determinism model, or the dual-runtime split ([ADR 0010](../../docs/adr/0010-content-generation-pipeline-architecture.md)). This feature is a conductor + a seam over the existing pipeline.
- **The production DeepSeek/LangGraph path and the HTTP admin trigger** — they already work and are not modified beyond possibly sharing the new CLI's env-wiring helpers.
- **New guardrail or QA logic** — the seam *calls* the existing evaluators; it does not add checks.
- **Distiller changes** — it already consumes `verdicts.jsonl`; Claude-runtime verdicts flow in unchanged.
- **Running Claude in CI / an automated end-to-end Claude run** — the Claude runtime is validated by construction, not by execution in the test suite.
- **The reader client** (mobile/web FE) — unrelated to generation.
- **Multi-run orchestration, queues, or scheduling** — one run at a time, driven by the operator.
- **Cross-engine mid-run handoff as a supported workflow** — the workspace is *interoperable* by construction, but starting on one engine and finishing on another is not a first-class, tested flow in V1.

## Further Notes

- **Parity is by construction, and this is the crux.** The Claude runtime cannot publish an out-of-contract constellation because it is forced through the same `harness check-*` gates and the same `harness publish` write that the production runtime uses; the seam's commands are covered by the Python suite, so the contract they enforce is tested once and shared.
- **The `researcher.md` placeholder was the tell** that the Claude runtime had never actually run: `tools: WebSourcePort` names a port, not a Claude Code tool. Making the grant real (`Bash` → `harness fetch`) is what turns the card from a spec into an executable subagent.
- **The operator walkthrough** in [`docs/running-a-generation-run.md`](../../docs/running-a-generation-run.md) will grow a `/new-constellation` section; the existing in-process-driver section stays and simply points at `harness run` once `scripts/gen.py` is folded in.
- **Suggested slice order for `/to-issues`** (tracer-bullet, each vertical and shippable): (1) the `harness` CLI skeleton + `check-piece`/`check-constellation` over the fixture substrate; (2) `fetch` + `verdict`; (3) `publish` + fold in `run`/`status`, delete `scripts/gen.py`; (4) the real tool grants + `.claude/agents/` regen (drift test); (5) the `/new-constellation` conductor skill + a manual verify run + the doc section.
