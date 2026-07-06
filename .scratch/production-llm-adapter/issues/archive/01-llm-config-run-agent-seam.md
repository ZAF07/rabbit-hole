# The seam — LLMConfig + the `run_agent` port method + `ToolSpec` + `ScriptedLLM.run_agent`

Status: completed
Feature: production-llm-adapter
Blocked by: none

## Parent

PRD: `.scratch/production-llm-adapter/PRD.md` (implements [ADR 0016](../../../docs/adr/0016-production-llm-adapter-and-bounded-worker-agents.md)).

## What to build

The prefactor that makes every later slice easy: widen the `LLMPort` to carry agent capability, add the provider config value object, and teach the offline fake to drive an agent loop — all landing green with **no real model** (ADR 0016 Decisions 1, 2).

- **`LLMConfig.from_env`** — a new harness config value object mirroring the store config pattern ([`content_graph/config.py`](../../../src/content_graph/config.py)): reads the provider selector, the API key, both DeepSeek V4 model-ids (precise/Flash and creative/Pro), and both tier temperatures from the environment (loading `.env` when no explicit mapping is passed). A missing or empty **required** value fails loud at construction with a message that names the absent variable (a `MissingConfigError`-style failure), so a deployment never launches only to die deep inside a run.
- **The port gains exactly one method** — `run_agent(request, tools, *, step_limit) -> str` alongside `complete`, so agent capability is a first-class seam, not a special case bolted onto `complete`. It returns JSON decoded by the same `decode.py` as every other call — one authority on response shape.
- **`ToolSpec`** — a framework-neutral frozen dataclass (`name`, `description`, `parameters` JSON schema, and a `run: (args) -> str` callable) living with the port. A stage describes _what a tool does_ without importing any agent framework.
- **`ScriptedLLM.run_agent`** — the offline fake implements `run_agent` too: it **invokes the supplied `ToolSpec` callables** (so the wrapped tools are genuinely exercised) and returns the purpose's scripted JSON, keeping the offline substrate whole so the agentic stages run end-to-end offline exactly like every other stage.

No adapter, no DeepSeek, no LangChain here — this slice is the domain-side seam and its fake, verifiable entirely offline.

## Acceptance criteria

- [x] `LLMConfig.from_env` reads the API key, both V4 model-ids, and both tier temperatures from an explicit mapping; when none is passed it loads `.env` and reads `os.environ`.
- [x] A missing or empty required config value raises a loud, `MissingConfigError`-style failure that **names the absent variable** — asserted by a test mirroring the store-config tests.
- [x] `LLMPort` exposes `run_agent(request, tools, *, step_limit) -> str` as an abstract method; `ToolSpec` is a frozen, framework-neutral dataclass with `name`, `description`, `parameters`, and a `(args) -> str` `run` callable.
- [x] `ScriptedLLM.run_agent` invokes the passed `ToolSpec` callables and returns scripted JSON, and records the request on `ctx.llm.requests` like `complete` does; the offline substrate still runs end-to-end.
- [x] Nothing in this slice imports LangChain or any provider SDK.
- [x] `uv run ruff check .`, `uv run ruff format`, `uv run mypy src`, and `uv run pytest` all pass.

## Blocked by

- None - can start immediately

## Completion

- Completed: 2026-07-06
- Commit: `0779fc0be9cfc374f70039827abe798e198a222c`
