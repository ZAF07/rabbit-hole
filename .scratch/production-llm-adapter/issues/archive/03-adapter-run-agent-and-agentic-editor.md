# Adapter `run_agent` + the agentic Editor over a `check_guardrails` tool

Status: completed
Feature: production-llm-adapter
Blocked by: 01, 02

## Parent

PRD: `.scratch/production-llm-adapter/PRD.md` (implements [ADR 0016](../../../docs/adr/0016-production-llm-adapter-and-bounded-worker-agents.md) Decisions 2, 3).

## What to build

The adapter's agent loop, plus the first stage to use it — the Editor. This is the tracer that proves an authored, bounded worker agent end-to-end, on the simpler of the two agentic stages (no browser, no new authored spec).

- **Adapter `run_agent`.** Behind the port, `run_agent` builds a `create_agent` loop over `ChatDeepSeek`, binds the passed `ToolSpec`s as tools, sets `recursion_limit` from `step_limit`, and returns the agent's final JSON (decoded by `decode.py`). `create_agent`, `ChatDeepSeek`, tool-binding, and `recursion_limit` live **entirely behind the adapter** — the domain and stages never import LangChain ([ADR 0014](../../../docs/adr/0014-harness-code-lives-in-src-harness.md)). The Editor's revision inherits the **creative** tier (V4 Pro).
- **The agentic Editor.** The Editor's machine-QA loop is reframed as a `run_agent` loop over a `check_guardrails` `ToolSpec` that wraps `evaluate_piece` **plus the LLM judge**, so the Editor sees the checker's verdict and revises again **within one bounded loop** instead of taking one blind shot per round.
- **The deterministic checker stays the arbiter.** `evaluate_piece() == clean` (plus the Stage-4.5 grounding check) decides a Piece is done _after_ the agent finishes — never the model's self-assessment. The loop is capped by `step_limit`; a Piece that still fails escalates to the human queue exactly as today (the existing budget-exceeded escalation).
- **Authored specs bound the agent (the anti-slop guarantee).** The Editor agent's `run_agent` request carries the assembled expert-authored `piece_spec + voice` as its `instructions`, exactly as today's `complete()` calls — **and** the `editor.judge` call nested inside the `check_guardrails` tool keeps `piece_spec + voice` too, so neither the agent nor its non-mechanical voice-checker is ever reduced to voice-blind violation-codes. This is a non-negotiable, test-asserted criterion.
- **Writer and Reviewer stay single-shot `complete()`** — an author must not grade its own draft, and a verdict stage must not loop on its own judgement. The agent _proposes_; code _disposes_.
- Adds an agent `step_limit` knob to `HarnessConfig` with a sane default.

## Acceptance criteria

- [x] The adapter's `run_agent` runs a `create_agent` tool loop, invokes a bound `ToolSpec`, honors `step_limit` via `recursion_limit`, and returns decodable JSON — asserted over the recorded HTTP transport (no real DeepSeek in CI); the Editor's revision goes out on the creative (V4 Pro) tier.
- [x] The domain and `stages.py` import only ports and `ToolSpec`; LangChain stays behind the adapter.
- [x] With `ScriptedLLM.run_agent` driving `check_guardrails`, the Editor loop revises until `evaluate_piece()` is clean; a Piece that cannot pass within `step_limit` still raises the existing budget-exceeded error and escalates, never silently ships.
- [x] A test asserts the Editor agent's recorded `run_agent` request carries the assembled `piece_spec + voice` as `instructions`, **and** the `editor.judge` call inside `check_guardrails` also carries `piece_spec + voice` — a refactor that drops either fails red.
- [x] The Writer (Draft) and Reviewer (QA) remain single-shot `complete()` calls.
- [x] The agentic Edit stage behaves identically under both runtimes (dual-runtime parity extended).
- [x] `uv run ruff check .`, `uv run ruff format`, `uv run mypy src`, and `uv run pytest` all pass.

## Blocked by

- production-llm-adapter/issues/01 (the `run_agent` port method, `ToolSpec`, and `ScriptedLLM.run_agent`)
- production-llm-adapter/issues/02 (the DeepSeek adapter foundation the `run_agent` loop builds on)

## Completion

- Completed: 2026-07-06
- Commit: `0779fc0be9cfc374f70039827abe798e198a222c`
