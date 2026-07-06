# API wiring lights the admin trigger + per-run `usage.json`

Status: completed
Feature: production-llm-adapter
Blocked by: 02, 05

## Parent

PRD: `.scratch/production-llm-adapter/PRD.md` (implements [ADR 0016](../../../docs/adr/0016-production-llm-adapter-and-bounded-worker-agents.md) Consequence / Trade-off; [ADR 0015](../../../docs/adr/0015-one-backend-deployable-http-api.md)).

## What to build

Turn the dormant admin generation-trigger live, and make real DeepSeek spend visible per run. Sequenced last so the go-live verification exercises the **full agentic, concurrent pipeline** end-to-end.

- **Go live by configuration.** `build_app_from_env` builds the real `LLMPort` via the provider factory (and the Playwright web port), constructs a generation service through the existing `build_generation_service`, and **mounts the admin trigger when the provider + `API_ADMIN_TOKEN` are configured** — enabling generation becomes a deployment setting, not a redeploy of new code. When the provider/token are absent, the trigger stays dormant exactly as today. The reader path imports none of it ([ADR 0015](../../../docs/adr/0015-one-backend-deployable-http-api.md)).
- **Per-run `usage.json`.** Each run writes a `usage.json` recording model calls and token/cost usage **per tier** (Flash-precise vs Pro-creative), so real DeepSeek spend is visible per run.
- **Provenance names the real models.** The run's recorded `runtime`/`model` identity — already stamped on every Verdict line — names the real DeepSeek models in production, so a Verdict's provenance reflects the models that produced it.
- **The boundary stays intact.** None of `run_agent`, `ToolSpec`, `LLMConfig`, the concurrency knobs, or `usage.json` is importable from or referenced by consumption ([ADR 0006](../../../docs/adr/0006-generation-and-consumption-are-separate.md)) — guarded by the existing import-boundary test.

## Acceptance criteria

- [x] With `LLM_PROVIDER` + a key + `API_ADMIN_TOKEN` configured, `build_app_from_env` wires a real generation service and the admin trigger is mounted and live; with any of them absent, the trigger stays dormant.
- [x] Each run writes a `usage.json` recording calls and token/cost usage broken down per tier.
- [x] The run's `runtime`/`model` identity on Verdict lines names the real configured DeepSeek models in production.
- [x] The import-boundary test still proves consumption imports none of `run_agent`, `ToolSpec`, `LLMConfig`, the concurrency knobs, or `usage.json`.
- [x] `/verify`: a real, small run against live DeepSeek + live pages (a 2–4 Piece Brief) reaches the piece gate — exercising thread-safety under real Chromium and real JSON-mode behavior together.
- [x] `uv run ruff check .`, `uv run ruff format`, `uv run mypy src`, and `uv run pytest` all pass.

## Blocked by

- production-llm-adapter/issues/02 (the factory + adapter `build_app_from_env` wires)
- production-llm-adapter/issues/05 (sequenced last so the go-live run exercises the full agentic, concurrent pipeline)

## Completion

- Completed: 2026-07-06
- Commit: `0779fc0be9cfc374f70039827abe798e198a222c`
