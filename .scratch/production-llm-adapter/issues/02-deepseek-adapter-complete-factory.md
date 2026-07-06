# The DeepSeek adapter (`complete`) + the provider factory + recorded-HTTP contract test

Status: ready-for-agent
Feature: production-llm-adapter
Blocked by: 01

## Parent

PRD: `.scratch/production-llm-adapter/PRD.md` (implements [ADR 0016](../../../docs/adr/0016-production-llm-adapter-and-bounded-worker-agents.md) Decisions 1, 4, 5).

## What to build

The first real `LLMPort` adapter's non-agentic half — `complete` — behind a provider factory, selected by config, and proven against a **recorded HTTP transport** so CI never hits real DeepSeek.

- **The DeepSeek adapter's `complete`** requests `response_format=json_object` on every call (structured decoding never depends on prompt-coaxed JSON) and applies a bounded **repair/transport retry**: it retries transport errors and non-parseable output a bounded number of times; `decode.py` stays the single authority on *shape*. A genuine, repeated contract mismatch (past the retry budget) raises the existing `LLMResponseError`, so "the model cannot produce this shape" is distinguishable from "the connection blipped."
- **Two tiers, chosen by request purpose.** A *tier* is a `(model, temperature)` pair: **V4 Flash at near-0** (*precise*) for the structural/judging purposes (plan, harvest, assess, refute, judge, ground, tier2), **V4 Pro at a higher temperature** (*creative*) for prose purposes (draft, revise, cut, hook). A single purpose→tier table, owned by the adapter, maps each purpose to its tier; both model-ids come from `LLMConfig` (env), so re-tiering or bumping a model is config, never code.
- **The provider factory** — a `{provider_name: builder}` registry and `build_llm(config)` returning the selected adapter. `LLM_PROVIDER=deepseek` is the only V1 entry; adding a second provider is a new adapter class + one registry line + a new `LLM_PROVIDER` value, and never touches the pipeline.
- **Optional extra + lazy imports.** A new `llm` optional extra (e.g. `langchain-deepseek`, `langchain`) mirroring the `web` extra; the adapter imports the provider SDK **lazily** so the core install stays provider-free and offline tests/CI never require it.
- **Build-time capability check.** Building the adapter verifies both configured V4 models support JSON mode, function calling, and `temperature`, so a model swap that breaks a later decision is caught before a run, not during one.
- **One env-gated live smoke test**, skipped unless a real key is present — the only thing that ever spends real DeepSeek budget.

`run_agent` on the adapter is **out of scope here** — it lands in slice 03 with its first consumer.

## Acceptance criteria

- [ ] `complete` sends `response_format=json_object` and selects the correct `(model, temperature)` tier by purpose — a precise purpose goes out as V4 Flash at near-0, a creative purpose as V4 Pro at the higher temperature — asserted over a recorded httpx transport injected into the client (no real DeepSeek in CI).
- [ ] The repair/transport retry recovers from a malformed-then-valid JSON sequence and from a transport-error-then-success sequence.
- [ ] A persistently malformed response (past the retry budget) surfaces as `LLMResponseError`, distinct from a transport blip.
- [ ] `build_llm(config)` returns the DeepSeek adapter for `LLM_PROVIDER=deepseek`; the registry shape makes a second provider a one-line addition.
- [ ] The harness stays fully installable and importable offline without the `llm` extra; the provider SDK is imported lazily.
- [ ] A build-time check fails loud if either configured V4 model lacks JSON mode, function calling, or `temperature` support.
- [ ] An env-gated live smoke test exists and is skipped when no real key is present.
- [ ] `uv run ruff check .`, `uv run ruff format`, `uv run mypy src`, and `uv run pytest` all pass.

## Blocked by

- production-llm-adapter/issues/01 (the `LLMConfig` the factory reads and the `LLMPort` the adapter implements)
