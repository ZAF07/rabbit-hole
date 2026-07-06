# PRD: The production LLM adapter — DeepSeek behind an agent-capable port, agents as bounded workers

Status: ready-for-agent
Feature: production-llm-adapter
Depends on: `generation-harness` (the gated pipeline, the `LLMPort`/`WebSourcePort` seams, the guardrail evaluators, the piece gate, the Distiller — all shipped)

> This PRD implements [ADR 0016](../../docs/adr/0016-production-llm-adapter-and-bounded-worker-agents.md): the first real `LLMPort` adapter (**DeepSeek**), the one port widening (`run_agent`) that lets two stages delegate *bounded* local decisions to a `create_agent` loop, bounded per-Piece concurrency, and collect-all-failures routing into the existing learning loop. It stays **generation-only** — nothing here crosses into consumption ([ADR 0006](../../docs/adr/0006-generation-and-consumption-are-separate.md)) — and it does **not** reopen the pipeline's shape ([ADR 0010](../../docs/adr/0010-content-generation-pipeline-architecture.md)): plan-first, the outcome contract, the human gates, the dual-runtime split, and determinism-by-construction all hold, because the agent lives behind the shared port, not in either runtime's orchestration.
>
> **Model-choice note:** [ADR 0016](../../docs/adr/0016-production-llm-adapter-and-bounded-worker-agents.md) Decision 5 was reconciled (2026-07-06) to the current DeepSeek **V4** line — **V4 Flash** (precise, near-0) for the structural + judging purposes and **V4 Pro** (creative, higher temperature) for prose — superseding the deprecated `deepseek-chat`/`deepseek-reasoner` framing. The ADR and this PRD now agree; a *tier* is a `(model, temperature)` pair chosen by request purpose.

## Problem Statement

The harness is fully built but **cannot generate anything real**. Every model call goes through the `LLMPort`, and the only adapter that exists is a scripted fake wired in tests and dev. The admin generation-trigger ([ADR 0015](../../docs/adr/0015-one-backend-deployable-http-api.md)) therefore ships **dormant**: `build_app_from_env` documents that it stays off "because no production LLM adapter exists yet." Until a real model sits behind the port, the whole generation subsystem is a design that has never produced a Piece.

Wiring a naive stateless adapter would light the trigger but leave real quality on the table in the two places where a human, working by hand, would *iterate*:

- **Sourcing.** The Researcher recalls candidate hub URLs and the stage chases their cited links with a fixed breadth-first walk ([`_chase_citations`](../../src/harness/pipeline/stages.py)). A blind fixed-depth crawl reaches *some* pages; it does not *navigate toward* a primary source the way a person following footnotes would.
- **Editing.** The Editor loops draft → evaluate → revise against the guardrails, but each revision is a single blind shot; the model never gets to *see the checker's output and try again within one turn*.

The team needs the first real model wired **without surrendering the determinism guarantees** that are the moat: anti-slop, grounding, and structural coherence must stay enforced by construction, the human must stay the final arbiter, and swapping DeepSeek for another provider later must be an adapter change, not a pipeline rewrite. And because a real run is several hundred model calls, it must be **concurrent enough to tolerate** and must **fail informatively** — surfacing every bad Piece in one pass rather than aborting on the first.

## Solution

Build **DeepSeek behind the existing `LLMPort`**, selected by config, and widen the port by exactly one method so two stages can delegate bounded navigation/revision to an agent loop that the stage's own deterministic checks still arbitrate.

1. **DeepSeek is an `LLMPort` adapter; the provider is a config choice.** `LLM_PROVIDER=deepseek` selects it through a small registry (an `llm_factory`); a new `src/harness/config.py` (`LLMConfig.from_env`, the same pattern the store configs use) reads the API key and the model/temperature knobs. Changing model, temperature, or key is pure environment. Adding a *provider* is a new adapter class + one registry line + flipping `LLM_PROVIDER`.

2. **The port gains one method: `run_agent`.** Alongside `complete(request) -> str`, the port gets `run_agent(request, tools, *, step_limit) -> str`, where `tools` are domain-neutral `ToolSpec`s (name, description, JSON schema, a `(args) -> str` callable). `create_agent`, `ChatDeepSeek`, tool-binding, and `recursion_limit` live **entirely behind the adapter**; the stages see only `ToolSpec` and get back JSON, decoded by the same `decode.py` as every other call. The hexagon holds — the domain never imports LangChain.

3. **Agents are bounded workers inside deterministic stages — not a supervisor.** Two stages delegate a *local* decision to a `run_agent` loop. **Both agents are bounded first by the expert-authored markdown, not only by `step_limit` and a checker tool.** Each `run_agent` call carries the assembled specs (Editorial DNA / Voice Profile / guardrail spec) in `LLMRequest.instructions` exactly as today's `complete()` calls do ([`ports/llm.py`](../../src/harness/ports/llm.py), whose `instructions` field is documented as "the markdown source of truth") — the agent's system prompt *is* the human's taste constitution, so the loop navigates and revises with editorial judgment instead of optimizing blindly against a checker or raw pages (the #1 failure mode: AI slop). This is a **non-negotiable acceptance criterion, symmetric across both agents**, and is asserted by a test on the recorded `run_agent` request (Testing Decisions, Seam 1).
   - **Researcher (Source)** gets a `fetch` `ToolSpec` (wrapping `WebSourcePort.fetch`) so it navigates cited outlinks *toward* primary sources ([ADR 0011](../../docs/adr/0011-harness-tools-are-ports-web-sourcing-recall-first.md)) instead of chasing them blindly. Because the citation-chase it replaces (`_chase_citations`) was **pure code — no model, no `instructions`** — navigation is a *new* authored decision-point: an expert-authored **"Navigation (Round 2a)" section is added to [`guardrails/sourcing.md`](../../harness/guardrails/sourcing.md)** (follow citation/footnote outlinks toward the primary tier, deprioritize nav-chrome, stop at a primary or at `step_limit`), and the nav agent carries `sourcing.md` as its `instructions` — parity with the existing `harvest`/`assess`/`refute` calls. The stage's **deterministic post-checks stay the arbiter**: per-page assessment, the **corroboration bar**, the refutation pass, and `ThinSourcePackError` all run *after* the agent and decide what is admitted.
   - **Editor (Edit)** gets a `check_guardrails` `ToolSpec` (wrapping `evaluate_piece` + the LLM judge) so it revises against a *deterministic* checker within one loop. Authored `piece_spec + voice` is preserved on **both** paths — the `run_agent` request's own `instructions` **and** the judge call nested inside the `check_guardrails` tool — so neither the agent nor its checker is ever reduced to voice-blind violation-codes (the judge is the *non-mechanical* voice check; stripped of the Voice Profile it goes blind, and the agent would satisfy the phrase-list while drifting off-voice). The stage's **`evaluate_piece() == clean`** (plus the Stage-4.5 grounding check) stays the arbiter; the agent's freedom is capped by `step_limit`, and a Piece that still fails escalates exactly as today.

   The **Writer (Draft)** and **Reviewer (QA)** stay single-shot `complete()` calls: an author must not grade its own draft, and a verdict stage must not loop on its own judgement. The agent *proposes*; code *disposes*.

4. **Structured output is JSON mode + an adapter-side repair/transport retry.** The adapter requests `response_format=json_object` and retries on transport errors and non-parseable output; `decode.py` stays the single authority on *shape*, failing loud on a genuine contract mismatch. Provider-agnostic (every OpenAI-compatible provider supports JSON mode) and no parallel schema per purpose.

5. **DeepSeek V4, split by purpose into two tiers** (superseding the ADR's deprecated `deepseek-chat`):
   - **Precise tier — V4 Flash at near-0 temperature** — for the structural and judging purposes (plan, harvest, assess, refute, judge, ground, tier2) and the Researcher's navigation agent. Cheap and stable where the output is structural.
   - **Creative tier — V4 Pro at a higher temperature** — for the prose purposes (draft, revise, cut, hook) and the Editor's revision agent. Strong where editorial quality is the moat.

   Each tier is a `(model, temperature)` pair chosen by request **purpose**; both model-ids are read from the environment (Decision 1), so re-tiering or bumping a model is config. Whichever V4 model a tier names **must** support JSON mode (Decision 4), function calling (Decision 2's `run_agent`/`create_agent`), and honor `temperature` — a verify-at-build check, not a V1 assumption.

6. **Bounded concurrency over the per-Piece fan-out.** Source, Draft, and Edit process Pieces through a `ThreadPoolExecutor` with a single bound `N` (a within-stage barrier, so the deliverable-on-disk gate and resume idempotence hold unchanged). Because Playwright launches a browser per fetch and its sync API is not freely thread-safe, fetching moves to a **thread-local browser** (one per worker thread, reused), bounding concurrent Chromium to the pool.

7. **Failures collect and escalate into the existing learning loop.** A concurrent fan-out stage no longer aborts on the first Piece to fail its bar: it lets every Piece finish, persists each failing artifact as the **machine copy** plus its failure code, and routes the failed Pieces into the **piece gate** as review targets. The human's fix is an ordinary **edit-approve Verdict** (diff-by-preservation, [ADR 0013](../../docs/adr/0013-human-review-surface-is-the-file-workspace.md)) the Distiller already consumes ([ADR 0004](../../docs/adr/0004-human-ratified-learning-loop.md)); an unfixable Piece becomes a non-**Survivor**, and rewire → reqa re-validate the structural invariants over the Survivors ([ADR 0012](../../docs/adr/0012-publish-gate-rewire-and-reqa-approved-subset.md)). **No new learning machinery.**

Once `LLM_PROVIDER` and a key are set, `build_app_from_env` wires a real generation service and the dormant admin trigger goes live.

## User Stories

*Actors: the **operator** (runs a batch and sets the deployment config), the **editor/curator** (the human arbiter at the gates who fixes and ratifies), the **developer** (builds and maintains the adapter and stages), and the **pipeline itself** (its agents and stages as system capabilities).*

**Provider selection & configuration (Decision 1, 5)**
1. As an operator, I want to select the model provider with a single `LLM_PROVIDER` environment variable, so that turning on real generation is a deployment setting, not a code change.
2. As an operator, I want the DeepSeek API key, both V4 model-ids (Flash and Pro), and both tier temperatures read from the environment (via `LLMConfig.from_env`, the same pattern as the store DSNs), so that no secret is ever baked into the image or a commit and re-tiering is config.
3. As an operator, I want a missing or empty API key (or model-id) to fail loud at startup with a message that names the missing variable, so that I never launch a deployment that will only fail deep inside a run.
4. As a developer, I want adding a new provider to be a new adapter class + one registry line + a new `LLM_PROVIDER` value, so that the second provider costs almost nothing and never touches the pipeline.
5. As a developer, I want V1 to use DeepSeek V4 in two tiers — **Flash (near-0) for structural/judging purposes, Pro (higher temperature) for prose purposes** — so that spend is low where the output is structural and quality is high where editorial prose is the moat.
6. As a developer, I want the tier (both its model and its temperature) chosen per request **purpose** (e.g. `architect.plan`/`editor.judge` → Flash-precise, `writer.draft`/`weaver.hook` → Pro-creative), so that the tiering is a property of the call, not a global knob.
7. As a developer, I want a build-time check that both configured V4 models support JSON mode, function calling, and temperature, so that a model swap that breaks Decisions 2 or 4 is caught before a run, not during one.
8. As an operator, I want the harness to remain fully installable and runnable offline without the LLM/agent dependencies (they sit behind an optional extra, lazily imported like Playwright), so that tests and CI never require a provider SDK.

**The port widening & the hexagon boundary (Decision 2)**
9. As a developer, I want the port to gain exactly one method — `run_agent(request, tools, *, step_limit) -> str` — alongside `complete`, so that agent capability is a first-class seam and not a special case bolted onto `complete`.
10. As a developer, I want tools passed as domain-neutral `ToolSpec`s (name, description, JSON schema, a `(args) -> str` callable), so that a stage describes *what a tool does* without importing any agent framework.
11. As a developer, I want `create_agent`, `ChatDeepSeek`, tool-binding, and `recursion_limit` to live entirely behind the adapter, so that the domain never imports LangChain and the hexagon holds ([ADR 0014](../../docs/adr/0014-harness-code-lives-in-src-harness.md)).
12. As a developer, I want `run_agent` to return JSON decoded by the same `decode.py` as every other call, so that there is one authority on response shape across the whole pipeline.
13. As a developer, I want the scripted fake to implement `run_agent` too — driving the supplied `ToolSpec` callables deterministically and returning scripted JSON — so that the agentic stages run end-to-end offline exactly like every other stage.

**Agentic Researcher — navigate toward sources (Decision 3)**
14. As the pipeline, I want the Researcher to navigate cited outlinks *toward* primary sources through a `fetch` tool, so that it citation-chases the way a person following footnotes would rather than crawling blindly at a fixed depth.
15. As the pipeline, I want the `fetch` tool to wrap the existing `WebSourcePort.fetch` (no new discovery surface — still no `search`), so that the corroboration bar and [ADR 0011](../../docs/adr/0011-harness-tools-are-ports-web-sourcing-recall-first.md)'s recall-first stance are untouched.
16. As the editor, I want every page the agent reaches still snapshotted into the run workspace, so that the sources behind a Piece remain inspectable regardless of how they were found.
17. As the pipeline, I want the deterministic corroboration bar, per-page assessment, and refutation pass to run *after* the agent and decide admission, so that the model's navigation never becomes the arbiter of what is verified.
18. As the pipeline, I want a Piece whose vetted claim pack is still too thin to raise `ThinSourcePackError` as it does today, so that a Piece still dies at research, not in prose.
19. As the pipeline, I want the agent's navigation capped by `step_limit`, so that a single Piece's sourcing cannot run away in link hops or spend.

**Agentic Editor — revise against a deterministic checker (Decision 3)**
20. As the pipeline, I want the Editor to revise against a `check_guardrails` tool that wraps `evaluate_piece` + the judge, so that it can see the checker's verdict and try again within one bounded loop instead of taking one blind shot per round.
21. As the pipeline, I want `evaluate_piece() == clean` (plus the Stage-4.5 grounding check) to remain the arbiter *after* the agent finishes, so that the deterministic checker, not the model's self-assessment, decides a Piece is done.
22. As the pipeline, I want the Editor's loop bounded by `step_limit`, and a Piece that still fails to escalate to the human queue exactly as it does today, so that the anti-slop guarantee is unchanged by making the loop agentic.
23. As a developer, I want the Writer (Draft) and Reviewer (QA) to stay single-shot `complete()` calls, so that an author never grades its own draft and a verdict stage never loops on its own judgement.

**Structured output & robustness (Decision 4)**
24. As a developer, I want the adapter to request `response_format=json_object` on every call, so that structured decoding does not depend on prompt-coaxed JSON.
25. As the pipeline, I want the adapter to transparently retry transport errors and non-parseable output a bounded number of times, so that a flaky connection or one malformed generation does not fail an entire run.
26. As a developer, I want `decode.py` to remain the single authority on response *shape* and to still fail loud on a genuine contract mismatch, so that a truly malformed generation is surfaced, not papered over by the retry layer.
27. As an operator, I want a genuine, repeated contract mismatch (after the adapter's retries) to raise the existing `LLMResponseError`, so that "the model cannot produce this shape" is distinguishable from "the connection blipped."

**Bounded concurrency (Decision 6)**
28. As an operator, I want Source, Draft, and Edit to process Pieces concurrently under a single configurable bound `N`, so that a several-hundred-call run completes in tolerable wall-clock time.
29. As the pipeline, I want each concurrent stage to be a within-stage barrier (all Pieces finish before the next stage starts), so that the deliverable-on-disk gate and resume idempotence hold exactly as in the serial pipeline.
30. As the pipeline, I want a resumed run to skip Pieces whose deliverable already exists, so that concurrency never re-does completed work or breaks resume-after-pause.
31. As the pipeline, I want the per-Piece deliverables written by a concurrent run to be identical to those a serial run would produce, so that concurrency is an efficiency change, never a content change.
32. As the pipeline, I want fetching to use a thread-local browser (one per worker thread, reused), so that Playwright's non-thread-safe sync API is respected and concurrent Chromium instances are bounded by the pool.
33. As an operator, I want the concurrency bound `N` to be a config knob with a sane default, so that I can tune throughput against provider rate limits without a code change.

**Collect-all-failures & the learning loop (Decision 7)**
34. As the editor, I want a concurrent fan-out stage to let *every* Piece finish rather than aborting on the first failure, so that I see all the run's problems in a single review pass, not one at a time across re-runs.
35. As the editor, I want each failing Piece persisted as its machine copy plus its failure code, so that I can review exactly what the pipeline produced and why it was rejected.
36. As the editor, I want failed Pieces routed into the **piece gate** as ordinary review targets, so that fixing them is the same edit-approve action as any other Verdict — no separate failure workflow.
37. As the editor, I want my fix recorded as an edit-approve Verdict via diff-by-preservation ([ADR 0013](../../docs/adr/0013-human-review-surface-is-the-file-workspace.md)), so that the machine→human diff becomes the richest possible learning signal the Distiller already consumes ([ADR 0004](../../docs/adr/0004-human-ratified-learning-loop.md)).
38. As the pipeline, I want an unfixable Piece to become a non-Survivor and rewire → reqa to re-validate the structural invariants over the Survivors ([ADR 0012](../../docs/adr/0012-publish-gate-rewire-and-reqa-approved-subset.md)), so that dropping a bad Piece never ships a broken Content Graph.
39. As a developer, I want **no new learning machinery** — failures reuse the existing gate, Verdict, and Distiller substrate — so that the learning loop stays one path.

**Going live & observability (Consequence, Trade-off)**
40. As an operator, I want `build_app_from_env` to wire a real generation service and light the admin trigger once `LLM_PROVIDER` + a key + `API_ADMIN_TOKEN` are set, so that enabling generation is configuration, not a redeploy of new code.
41. As an operator, I want each run to write a `usage.json` recording model calls and token/cost usage (per tier), so that real DeepSeek spend is visible per run.
42. As the editor, I want the run's recorded `runtime`/`model` identity (already stamped on every Verdict line) to name the real DeepSeek models, so that a Verdict's provenance reflects the models that produced it.
43. As a developer, I want the dual-runtime parity guarantee preserved — the agentic stages behave identically under LangGraph and the Claude Code wiring because the agent lives behind the shared port — so that [ADR 0010](../../docs/adr/0010-content-generation-pipeline-architecture.md)'s split is not reopened.
44. As a developer, I want the ADR 0006 boundary untouched: none of `run_agent`, `ToolSpec`, `LLMConfig`, concurrency, or `usage.json` is importable from or referenced by consumption.

**Authored specs bound the agents (Decision 3 — the anti-slop guarantee for the agentic path)**
45. As the pipeline, I want each bounded-worker agent's system prompt to be the assembled expert-authored markdown (Editorial DNA / Voice Profile / guardrail spec) carried in `LLMRequest.instructions` exactly as today's `complete()` calls, so that the agent revises and navigates with the human's editorial taste and cannot optimize blindly against a checker or raw pages (AI slop).
46. As the editor, I want the Researcher's *new* navigation decision-point governed by an expert-authored **"Navigation (Round 2a)"** section in `guardrails/sourcing.md` (follow citation/footnote outlinks toward the primary tier, deprioritize nav-chrome, stop at a primary or at `step_limit`), so that a model decision-point that did not exist when navigation was pure code still has human taste behind it.
47. As the pipeline, I want the Editor's authored `piece_spec + voice` preserved on both the `run_agent` request *and* the judge call inside the `check_guardrails` tool, so that neither the agent nor its non-mechanical voice-checker is ever reduced to voice-blind violation-codes.
48. As a developer, I want a test asserting both agents' recorded `run_agent` requests carry the assembled authored `instructions`, so that a refactor which silently drops the specs fails red instead of shipping a rudderless agent.
49. As a developer, I want the authored-instruction changes to keep the two runtimes at parity — both read the same authored files — so that if the navigation heuristic ever moves out of `sourcing.md`, the Researcher card's **"Reads:"** line is updated in the same change and Claude Code never diverges from LangGraph.

## Implementation Decisions

*Paths are named where they already exist or where the ADR fixes them; treat them as the current shape, not a contract — they may move during implementation.*

**Modules built or modified**

- **`src/harness/config.py` (new)** — `LLMConfig.from_env(env=None)`, mirroring [`content_graph/config.py`](../../src/content_graph/config.py): reads the provider selector, API key, the two V4 model-ids (precise/Flash and creative/Pro), and the two tier temperatures from the environment (loading `.env` when no explicit mapping is passed); raises a `MissingConfigError`-style loud failure when a required value is absent.
- **`src/harness/ports/llm.py` (modified)** — add `run_agent(self, request: LLMRequest, tools: Sequence[ToolSpec], *, step_limit: int) -> str` to the `LLMPort` ABC, and define `ToolSpec` (a frozen dataclass: `name`, `description`, `parameters` JSON schema, and `run: Callable[[Mapping[str, object]], str]`). `ToolSpec` is framework-neutral and lives with the port.
- **`src/harness/adapters/deepseek.py` (new)** — the production `LLMPort` adapter. `complete` requests `response_format=json_object` and applies the repair/transport retry; `run_agent` builds a `create_agent` loop over `ChatDeepSeek`, binds the `ToolSpec`s as tools, sets `recursion_limit` from `step_limit`, and returns the agent's final JSON. The `(model, temperature)` tier is selected per request purpose (Flash-precise vs Pro-creative). All LangChain imports are lazy (offline installs never need them).
- **`src/harness/adapters/llm_factory.py` (new)** — a `{provider_name: builder}` registry and a `build_llm(config)` that returns the selected adapter; `LLM_PROVIDER=deepseek` is the only V1 entry.
- **Purpose→tier map** — a single table classifying each request purpose as precise or creative, owned by the adapter (or a small helper it reads); the two agent purposes classify with their stage (Researcher navigation → precise, Editor revision → creative).
- **`src/harness/adapters/fakes.py` (modified)** — `ScriptedLLM` gains `run_agent`: it invokes the supplied `ToolSpec` callables (so the fetch/guardrail tools are genuinely exercised) and returns the purpose's scripted JSON, keeping the offline substrate whole.
- **`src/harness/adapters/playwright_web.py` (modified)** — browser creation moves behind an **injectable browser-factory** and a thread-local cache: one browser per worker thread, reused across that thread's fetches, torn down with the pool. The public `fetch` surface is unchanged.
- **`src/harness/pipeline/stages.py` (modified)** — `run_stage_source`'s citation-chasing (`_chase_citations`) is reframed as a `run_agent` navigation over a `fetch` `ToolSpec`, with the deterministic assess/corroborate/refute/thin-pack checks unchanged downstream. `run_stage_edit`'s QA loop (`_qa_loop`) is reframed as a `run_agent` loop over a `check_guardrails` `ToolSpec`, with `evaluate_piece`/grounding-check unchanged as the post-agent arbiter. **Both agentic stages carry the assembled expert-authored specs in the `run_agent` request's `instructions` exactly as today's `complete()` calls do** — the nav agent gets `sourcing.md` (incl. its new Navigation section), the Editor agent gets `piece_spec + voice`, and the Editor's `check_guardrails` tool keeps `piece_spec + voice` on its embedded `editor.judge` call. Source, Draft, and Edit each fan their per-Piece work out through a bounded `ThreadPoolExecutor` and **collect** rather than abort on the first failure.
- **`harness/guardrails/sourcing.md` (modified — authored, not code)** — gains an expert-authored **"Navigation (Round 2a)"** section (follow citation/footnote outlinks toward the primary tier, deprioritize nav-chrome, stop at a primary or at `step_limit`); it is the nav agent's authored instruction source under both runtimes, because the Researcher card already declares it **Reads `guardrails/sourcing.md`** — so LangGraph (via `instructions`) and Claude Code (via the subagent reading the file) stay at parity. If navigation ever moves to its own spec file, the Researcher card's **"Reads:"** line must change in the same commit.
- **`src/harness/pipeline/context.py` (modified)** — `HarnessConfig` gains a concurrency bound (e.g. `fan_out`) and an agent `step_limit` knob, with sane defaults; the existing `model`/`runtime` identity fields carry the real DeepSeek model names in production.
- **Failure routing (modified where the piece gate is fed)** — a stage that collected failures records each failing Piece's machine copy + failure code and marks it a piece-gate review target; the existing `human_gate_update` per-piece path ([`steps.py`](../../src/harness/pipeline/steps.py)) and rewire/reqa Survivor logic consume it unchanged.
- **`src/api/main.py` / `src/api/harness_runner.py` (modified)** — `build_app_from_env` builds the real `LLMPort` via the factory (and the Playwright web port), constructs a generation service through `build_generation_service`, and mounts the admin trigger when the provider + admin token are configured; the reader path imports none of it ([ADR 0015](../../docs/adr/0015-one-backend-deployable-http-api.md)).
- **`pyproject.toml` (modified)** — a new optional extra (e.g. `llm = ["langchain-deepseek", "langchain"]`) mirroring the `web` extra; the core install stays provider-free.

**Interfaces / contracts**

- `LLMPort.run_agent(request, tools, *, step_limit) -> str` returns JSON; `decode.py` decodes it. `ToolSpec.run(args) -> str` returns the tool's result as a string the agent reads.
- `LLMConfig.from_env` is the sole reader of provider credentials/knobs (API key, both V4 model-ids, both tier temperatures); the factory maps `LLM_PROVIDER` → adapter, and the adapter maps request purpose → `(model, temperature)` tier.
- The web port surface is unchanged (`fetch(url) -> FetchedPage | None`, no `search`); only the adapter's internal browser lifecycle changes.
- Collected-failure routing produces the same review targets and Verdict shape the piece gate already handles — no new gate, no new Verdict kind.

**Architectural invariants preserved**

- The hexagon: LangChain/Playwright/DeepSeek stay behind adapters; the domain and stages import only ports and `ToolSpec`.
- **Authored specs bound the agents:** both bounded-worker agents' system prompts are the expert-authored markdown (DNA / Voice / guardrail) via `LLMRequest.instructions`, not just `step_limit` + a checker tool — the anti-slop guarantee for the agentic path, and the reason both runtimes stay at parity (they read the same authored files).
- ADR 0010's pipeline shape (plan-first, outcome contract, three human gates, dual-runtime, determinism-by-construction) is untouched — the agent is inside a stage, behind the port, not in the orchestration.
- The ADR 0006 boundary: nothing here is importable from consumption (guarded by the existing import-boundary test).

## Testing Decisions

**What makes a good test here:** assert *external, observable behavior* at a port or deliverable, never an implementation detail. A stage test asserts the *deliverable on disk* and the *requests the stage issued through the port* (the existing `ctx.llm.requests` / `ctx.web.fetched` pattern), not the internal control flow. An adapter test asserts *what went out on the wire and what the adapter did with what came back*, never LangChain internals.

**Seam 1 — `LLMPort`(+`run_agent`) and `WebSourcePort`, driven at `build_context`** (`tests/harness/pipeline/…`). The dominant seam; carries the bulk of the ADR:
- **Authored specs reach the agents (D3 — the anti-slop guarantee):** assert both agents' recorded `run_agent` requests carry the assembled expert-authored `instructions` — the nav agent's request carries `sourcing.md` *including its new Navigation (Round 2a) section*, and the Editor agent's request **and** the `editor.judge` call inside its `check_guardrails` tool carry `piece_spec + voice` — via the existing `ctx.llm.requests` capture, so a refactor that drops the specs fails red rather than shipping a rudderless agent.
- **Agentic Source (D3):** with `ScriptedLLM.run_agent` driving a `fetch` tool over `FakeWebSource`, assert a primary source is reached by navigation, the corroboration bar / `ThinSourcePackError` still decide admission, and `step_limit` bounds the walk. Extends the existing `test_source_stage.py`.
- **Agentic Edit (D3):** with `run_agent` driving `check_guardrails`, assert the loop revises until `evaluate_piece()` is clean, and a Piece that cannot pass within `step_limit` still raises `QABudgetExceededError` / escalates. Extends `test_draft_edit_stages.py`.
- **Concurrency (D6):** assert a fan-out run produces byte-identical deliverables to a serial run (determinism), skips existing deliverables on resume, and honors the bound `N`.
- **Collect-all-failures (D7):** script one Piece to fail its bar; assert the stage still finishes the others, persists the failing machine copy + failure code, routes the failure into the piece gate, and that an edit-approve Verdict + rewire/reqa yields a contract-valid Survivor set. Extends `test_publish_gate.py` / `test_review_surface.py`.
- **Dual-runtime parity:** the agentic stages behave identically under both runtimes — extend `test_dual_runtime_parity.py`.

**Seam 2 — the DeepSeek adapter over a recorded httpx transport** (`tests/harness/adapters/test_deepseek_adapter.py`, new). Inject a replayed HTTP transport into `ChatDeepSeek` so real DeepSeek is never hit in CI:
- `complete` sends `response_format=json_object` and selects the right `(model, temperature)` tier by purpose — a precise purpose goes out as V4 Flash at near-0, a creative purpose as V4 Pro at the higher temperature.
- The repair/transport retry recovers from a malformed-then-valid JSON sequence and from a transport-error-then-success sequence.
- A persistently malformed response (past the retry budget) surfaces as `LLMResponseError` — "cannot produce this shape" is distinct from "connection blipped."
- `run_agent` runs the `create_agent` tool loop, invokes a bound `ToolSpec`, honors `step_limit` via `recursion_limit`, and returns decodable JSON.
- One **opt-in, env-gated live smoke test** (skipped unless a real key is present) is the only thing that ever spends real DeepSeek budget.

**Seam 3 — the injectable browser-factory inside `PlaywrightWebSource`** (`tests/harness/adapters/test_playwright_web.py`, new). With a fake browser-factory, assert exactly one browser is created per worker thread and reused across that thread's fetches (thread-safety as a fast offline assertion), and that a navigation failure still returns `None`. No real Chromium in CI.

**Config (`tests/harness/test_llm_config.py`, new):** `LLMConfig.from_env` reads the API key, both V4 model-ids, and both tier temperatures from an explicit mapping; a missing required value fails loud naming the variable — mirrors the store-config tests.

**API wiring (`tests/api/…`, extend):** the admin trigger goes live when the provider + admin token are configured and stays dormant otherwise; the import-boundary test still proves consumption imports none of this. Extends `test_admin_api.py` / `test_import_boundary.py` / `test_harness_trigger_integration.py`.

**Prior art to follow:** `tests/harness/fixture_run.py` (the offline substrate and `ScriptedLLM`/`FakeWebSource` pattern), `tests/harness/pipeline/test_source_stage.py` and `test_draft_edit_stages.py` (asserting deliverables + issued requests), `tests/harness/pipeline/test_publish_gate.py` (Survivor/rewire/reqa), and the store-config tests for `from_env`.

## Out of Scope

- **Any DeepSeek model beyond the V4 Flash + Pro tiers** — no `deepseek-reasoner` (V4 supersedes it), no third tier; the two-tier split is V1.
- **A second provider** — the factory is built to make one cheap later, but only `deepseek` ships.
- **A `search(query)` web-sourcing surface** — the port stays `fetch`-only; a SERP adapter is a later, separate decision ([ADR 0011](../../docs/adr/0011-harness-tools-are-ports-web-sourcing-recall-first.md)).
- **New learning machinery** — failures reuse the existing piece gate, Verdict, and Distiller; nothing new is added to the learning loop (D7).
- **Any change to the pipeline's shape** — no new stages, gates, or outcome-contract changes; the agent lives *inside* existing stages (D3, [ADR 0010](../../docs/adr/0010-content-generation-pipeline-architecture.md)).
- **The reader client** and any consumption-side change — untouched ([ADR 0006](../../docs/adr/0006-generation-and-consumption-are-separate.md)).
- **Cross-stage / cross-Piece parallelism** — concurrency is bounded, within-stage, per-Piece only; stages still run in fixed order (D6).
- **Async I/O** — concurrency is a `ThreadPoolExecutor`, not an asyncio rewrite of the pipeline.

## Further Notes

- **ADR 0016 Decision 5 was reconciled** (2026-07-06) to the DeepSeek V4 Flash + Pro per-purpose split, so the design record and this PRD agree.
- The ADR is explicit that this is **heavier** than a stateless adapter (an agent loop, a tool abstraction, thread-safe concurrency, a reworked web adapter) and accepts the cost because the agentic stages are exactly where the model does work a human otherwise would; `usage.json` and the recorded-HTTP contract test bound the two risks (real spend, larger test surface).
- Suggested slicing into tracer-bullet issues (each a vertical slice ending green): **(1)** `LLMConfig` + the `run_agent` port method + `ToolSpec` + `ScriptedLLM.run_agent` (the seam, offline); **(2)** the DeepSeek adapter + factory + recorded-HTTP contract test (`complete`, JSON mode, retries, the Flash/Pro tier routing); **(3)** `run_agent` on the adapter + the agentic Editor over `check_guardrails`; **(4)** the agentic Researcher over `fetch` + the thread-local browser-factory; **(5)** bounded per-Piece concurrency + collect-all-failures routing into the piece gate; **(6)** the API wiring that lights the admin trigger + `usage.json`. Order and boundaries are a suggestion for `/to-issues`, not a contract.
- `/verify` for this feature means a real, small run against live DeepSeek + live pages (a 2–4 Piece Brief) reaching the piece gate — the only place thread-safety under real Chromium and real JSON-mode behavior are exercised together.
