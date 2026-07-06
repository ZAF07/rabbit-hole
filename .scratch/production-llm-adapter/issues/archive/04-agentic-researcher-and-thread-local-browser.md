# The agentic Researcher over a `fetch` tool + the thread-local browser-factory

Status: completed
Feature: production-llm-adapter
Blocked by: 01, 03

## Parent

PRD: `.scratch/production-llm-adapter/PRD.md` (implements [ADR 0016](../../../docs/adr/0016-production-llm-adapter-and-bounded-worker-agents.md) Decision 3; [ADR 0011](../../../docs/adr/0011-harness-tools-are-ports-web-sourcing-recall-first.md)).

## What to build

The second bounded-worker agent — the Researcher — navigating cited outlinks _toward_ primary sources through a `fetch` tool, plus the web-adapter rework that makes concurrent fetching safe.

- **The agentic Researcher.** The Source stage's blind, fixed-depth citation-chase is reframed as a `run_agent` navigation over a `fetch` `ToolSpec` that **wraps the existing `WebSourcePort.fetch`** (no new discovery surface — still no `search`, [ADR 0011](../../../docs/adr/0011-harness-tools-are-ports-web-sourcing-recall-first.md)'s recall-first stance untouched). The agent follows citation/footnote outlinks toward the primary tier the way a person following footnotes would, instead of crawling breadth-first at a fixed depth. Its navigation is capped by `step_limit` so one Piece's sourcing can't run away in link hops or spend.
- **A new authored decision-point.** Because the citation-chase it replaces was **pure code — no model, no `instructions`** — navigation is a _new_ authored decision-point. Add an expert-authored **"Navigation (Round 2a)"** section to `harness/guardrails/sourcing.md` (follow citation/footnote outlinks toward the primary tier, deprioritize nav-chrome, stop at a primary or at `step_limit`). The nav agent carries `sourcing.md` — including this new section — as its `instructions`, at parity with the existing harvest/assess/refute calls. The Researcher agent card already declares it **Reads `guardrails/sourcing.md`**, so LangGraph (via `instructions`) and Claude Code (via the subagent reading the file) stay at parity; **if navigation ever moves to its own spec file, the Researcher card's "Reads:" line must change in the same commit.**
- **The deterministic post-checks stay the arbiter.** Per-page assessment, the **corroboration bar**, the refutation pass, and `ThinSourcePackError` all run _after_ the agent and decide what is admitted — the model's navigation never becomes the arbiter of what is verified. Every page the agent reaches is still snapshotted into the run workspace, so the sources behind a Piece stay inspectable regardless of how they were found. A Piece whose vetted claim pack is still too thin raises `ThinSourcePackError` as it does today — dies at research, not in prose.
- **Thread-local browser-factory.** Because Playwright launches a browser per fetch and its sync API is not freely thread-safe, browser creation moves behind an **injectable browser-factory** with a **thread-local cache**: one browser per worker thread, reused across that thread's fetches, torn down with the pool. The public `fetch(url) -> FetchedPage | None` surface is unchanged; only the internal browser lifecycle changes. This is the prerequisite that makes slice 05's concurrent Source fan-out safe.

## Acceptance criteria

- [x] With `ScriptedLLM.run_agent` driving a `fetch` tool over the faked web source, the Researcher reaches a primary source **by navigation** (following a recalled hub's cited outlinks), not by any `search` call — there is no `search` on the port surface.
- [x] The corroboration bar / per-page assessment / refutation pass run _after_ the agent and decide admission; a still-thin claim pack raises `ThinSourcePackError` before the Draft stage runs.
- [x] `step_limit` bounds the navigation walk.
- [x] Every page the agent reaches is snapshotted into the run workspace.
- [x] `harness/guardrails/sourcing.md` gains an expert-authored "Navigation (Round 2a)" section, and a test asserts the nav agent's recorded `run_agent` request carries `sourcing.md` **including that section** as its `instructions`.
- [x] The injectable browser-factory creates exactly one browser per worker thread and reuses it across that thread's fetches (fast offline assertion with a fake factory); a navigation failure still returns `None`. No real Chromium in CI.
- [x] The agentic Source stage behaves identically under both runtimes (dual-runtime parity extended).
- [x] `uv run ruff check .`, `uv run ruff format`, `uv run mypy src`, and `uv run pytest` all pass.

## Blocked by

- production-llm-adapter/issues/01 (the `run_agent` port method, `ToolSpec`, and `ScriptedLLM.run_agent`)
- production-llm-adapter/issues/03 (the adapter's `run_agent` loop, first proven on the Editor)

## Completion

- Completed: 2026-07-06
- Commit: `0779fc0be9cfc374f70039827abe798e198a222c`
