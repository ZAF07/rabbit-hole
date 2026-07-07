# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

**Rabbit Hole** — a consumer **intellectual-curiosity** app: curated, narrative content users travel through by following **Connections** between topics, so they *see how things in the world connect*. Lighter than a course, deeper than TikTok. The moat is **editorial taste**, not AI sophistication; the #1 failure mode to avoid is **AI slop**. See `README.md` / `IDEA.md` for the vision and `CONTEXT.md` for the domain language.

The system is **two independent subsystems joined only by the Content Graph** ([ADR 0006](docs/adr/0006-generation-and-consumption-are-separate.md)):

- **Generation** — the content **harness** (`harness/`): an agentic pipeline that generates, grounds, and wires Pieces, Connections, and hooks, and writes them into the Content Graph. It knows nothing about users or the app.
- **Consumption** — the **app** (`src/consumption/` + `src/api/`): the reader experience. It reads *only* Pieces and Connections from the Content Graph. It knows nothing about how content was made.

Nothing but **Pieces, Connections, and Topics** crosses the boundary. Keep it that way.

## Current state

The design record is complete, and **all three subsystems' backends are built**: the **Content Graph** (`src/content_graph/` — port + in-memory and Postgres adapters, migrations, docker-compose), the **generation harness** (`src/harness/` — the full gated pipeline under both runtimes, guardrail evaluators, grounding, human review surface, publish gate, Distiller; see [ADR 0014](docs/adr/0014-harness-code-lives-in-src-harness.md)), and the **consumption backend** (`src/consumption/` app-service + `src/api/` — the one FastAPI deployable with the reader router and the async admin generation-trigger; see [ADR 0015](docs/adr/0015-one-backend-deployable-http-api.md)). The **production LLM adapter is now built** ([ADR 0016](docs/adr/0016-production-llm-adapter-and-bounded-worker-agents.md)): **DeepSeek behind the `LLMPort`** selected by config (`src/harness/config.py`, `adapters/deepseek.py`, `adapters/llm_factory.py`), the one-method port widening (`run_agent` + `ToolSpec`) that lets the Researcher and Editor run as **bounded-worker agents**, a thread-local Playwright browser with **bounded per-Piece concurrency** (`fan_out`), collect-all-failures routing into the piece gate, and per-run `usage.json`. `build_app_from_env` now **lights the admin generation-trigger by config** — set `LLM_PROVIDER` + `API_ADMIN_TOKEN` and it goes live; leave them unset and it stays dormant exactly as before. The `LLMPort` is still scripted in tests/dev (offline substrate). What remains is the **reader client** (the mobile/web FE that renders these responses).

## Read before working (the design record)

| File | What it holds |
| --- | --- |
| `CONTEXT.md` | Domain glossary — the canonical vocabulary. Use these terms; don't drift to synonyms listed under *Avoid*. |
| `docs/adr/0001–0017` | Architecture Decision Records — decisions not to re-litigate. |
| `docs/experience.md` | Consumption-side design: Piece schema, Content Blocks, Session, Tapestry, retention. |
| `docs/content-harness.md` | Generation-side design: the pipeline, grounding, learning loop, determinism. |
| `docs/taxonomy.md` | Seed Topic taxonomy. |
| `harness/` | The harness's living specs — Editorial DNA + Voice Profiles, guardrails, agent roster. |

If your work moves the domain model (new terms/decisions), update `CONTEXT.md` / `docs/adr/` via `/domain-modeling` so they don't drift.

## Architecture & tech stack

- **Language:** Python (3.12+), managed with **uv**.
- **Pattern:** **ports-and-adapters (hexagonal)** for both subsystems — domain logic depends on ports (interfaces); adapters (DB, LLM, web search) are swappable at the edges. (https://8thlight.com/insights/a-color-coded-guide-to-ports-and-adapters)
- **Data store — the Content Graph:** **Postgres**. Local dev via **Docker** (docker-compose); scale via **Supabase** (managed Postgres). Because the store sits behind a port with a Postgres adapter, **Docker ↔ Supabase is a connection-config swap, not a code change.**
- **Generation runtime (dual):** a deterministic **LangGraph `StateGraph`** (production; guarantees the outcome contract) *and* **Claude Code skills/agents** (interactive/dev/human-review) — both read the same markdown specs + a shared stage manifest ([ADR 0010](docs/adr/0010-content-generation-pipeline-architecture.md)).
- **The Content Graph is the only coupling** between generation and consumption: generation writes; consumption reads. Neither imports the other.
- **Client surface** (mobile/web reader): a later decision; the consumption backend is Python + Postgres.

## Directory map

| Path | Purpose |
| --- | --- |
| `harness/editorial/` | Editorial DNA + swappable **Voice Profiles** (the taste constitution). |
| `harness/guardrails/` | Anti-slop + sourcing checks (`piece`, `connection`, `constellation`, `sourcing`). |
| `harness/agents/` | The 7 agent spec-cards (Architect…Distiller); `.claude/agents/` is generated from this file. |
| `harness/manifest.toml` | The shared stage manifest both runtimes read (stages, deliverables, human gates). |
| `harness/runs/<id>/` | Per-run workspaces (gitignored): `plan.md`, `pieces/<id>/…`, `connections.md`, `qa.md`, `publish/`, `feedback/verdicts.jsonl`. |
| `src/harness/` | Generation code: the gated pipeline (LangGraph + manifest runner), guardrail evaluators, ports/adapters, review surface, Distiller ([ADR 0014](docs/adr/0014-harness-code-lives-in-src-harness.md)). |
| `src/content_graph/` | The Content Graph: domain models, `ContentGraphRepository` port, in-memory + Postgres adapters, migrations. |
| `src/consumption/` | Consumption backend: the reader use-cases (app-service), domain, ports, in-memory + Postgres adapters, presentation vocabulary. |
| `src/api/` | The single backend deployable — one FastAPI app: reader router + async admin generation-trigger, response DTOs, anonymous identity ([ADR 0015](docs/adr/0015-one-backend-deployable-http-api.md)). |
| `.claude/agents/` | Generated Claude Code subagents — regenerate from `harness/agents/README.md`; a drift test guards them. |
| `docs/adr/`, `CONTEXT.md` | The design record (above). |
| `.scratch/<feature>/` | Local issue tracker — PRDs + issues as markdown (see `docs/agents/issue-tracker.md`). |

## Coding standards

- Type-annotate all public functions; `mypy` must pass on `src/`.
- Use absolute imports, not relative.
- Use **uv** for packages and the virtual env.
- Keep functions focused; prefer pure functions and dependency injection over globals.
- Clear, descriptive names for functions and variables.
- All methods have **google-style docstrings** (what it does, params, returns). No inline comments — put them in the docstring if truly needed.
- Match the style of surrounding code.
- No secrets, API keys, or tokens in code or commits — read them via `config.py` / `.env`.
- New code comes with tests. A task isn't done until `pytest`, `ruff`, and `mypy` pass — and say so explicitly, with output, if any fail.
- Follow ports-and-adapters — keep the domain free of framework/DB/LLM detail; push those to adapters.

## How I want you to work (process)

- **Plan before large changes.** Outline the approach first for anything non-trivial.
- **Small, reviewable steps.** Incremental edits over sweeping rewrites.
- **Verify, don't assume.** Run the command; report the real result.
- **Ask when genuinely blocked** on a decision only I can make; otherwise pick the sensible default, state it, and proceed.
- **Don't stage, commit, or push** unless I ask.
- **Respect the boundary.** Never let consumption read generation-only concepts (run id, constellation, grounding ledger); never let generation depend on user/session data ([ADR 0006](docs/adr/0006-generation-and-consumption-are-separate.md)).

## Development workflow (router)

Every piece of work gets an issue file in `.scratch/<feature>/issues/` **before** code changes — the cross-session anchor.

**New feature:**
1. `/grill-with-docs` — sharpen the idea; ADRs and `CONTEXT.md` land as decisions are made.
2. `/to-prd` — synthesize into `.scratch/<feature>/PRD.md`.
3. `/to-issues` — break into tracer-bullet vertical slices with `Blocked by:` dependencies.
4. Per issue, on a branch: `/implement <issue path>` — TDD at agreed seams, quality gates, then `/code-review`.
5. `/verify` — confirm it works in the running system, not just green tests.
6. `/post-implement` — verify acceptance criteria with evidence, mark completed, archive. Then `/domain-modeling` if the domain moved.

**Improve existing code:** `/simplify` (diff-scoped) or `/improve-codebase-architecture`; funnel into an issue, then steps 4–6.

**Debugging:** `/file-bug` → `/diagnosing-bugs` → fix test-first with `/tdd` → `/verify` → `/code-review` → `/post-implement`. A bug is a defect in **already-shipped** code; a broken function in the current diff is fixed in place, not filed.

## Definition of done

1. Code imports/compiles and the change is **verified in the running system** (`/verify`), not just green in tests.
2. `uv run ruff check .`, `uv run ruff format`, `uv run mypy src`, and `uv run pytest` all pass.
3. New behavior has tests; a bug fix has a test red-before / green-after.
4. Acceptance criteria checked off with evidence; changes and caveats reported plainly.

## Agent skills

### Issue tracker
Issues and PRDs are tracked as local markdown files under `.scratch/<feature>/`; external PRs are not a triage surface. See `docs/agents/issue-tracker.md`.

### Triage labels
Five canonical triage roles with default strings (`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`), recorded as a `Status:` line in each issue file. See `docs/agents/triage-labels.md`.

### Domain docs
Single-context: one `CONTEXT.md` + `docs/adr/` at the repo root. See `docs/agents/domain.md`.
