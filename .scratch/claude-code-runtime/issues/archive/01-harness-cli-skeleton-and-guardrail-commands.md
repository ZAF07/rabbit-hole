# 01 — `harness` CLI skeleton + `check-piece` / `check-constellation`

Status: completed
Feature: claude-code-runtime

## Parent

PRD: [.scratch/claude-code-runtime/PRD.md](../PRD.md) · [ADR 0019](../../../docs/adr/0019-claude-code-generation-runtime-and-shared-harness-cli.md)

## What to build

The foundation of the shared **`harness` CLI** seam, carried end-to-end by the two guardrail commands. Introduce a first-class console script (`harness`, registered in `pyproject.toml`) split into a **testable core** — a `run_cli(argv, *, ports…)`-style function that executes a subcommand over injected ports/workspace/specs and returns an exit code while writing structured JSON to stdout — and a **thin `main()`** that resolves the real adapters from environment config exactly as `build_app_from_env` does for the API (Postgres, DeepSeek, Playwright, `SpecLibrary`, `HARNESS_ROOT`/`HARNESS_FAN_OUT`). No new secret surface.

The two commands proving the seam:

- `harness check-piece <run_id> <piece_id>` — parse the Piece from the run workspace, run `evaluate_piece` (with banned phrases from `SpecLibrary`), print the violations as JSON, exit non-zero if any.
- `harness check-constellation <run_id>` — run `evaluate_constellation` / `evaluate_connections` over the run, print the Tier-1 invariant (I1–I8) + anti-slop + ledger results as JSON, exit non-zero on any violation.

Both are **thin adapters** over already-shipped pure functions — this slice adds wiring, arg dispatch, and the exit-code/stdout contract, not guardrail logic. This is generation-only ([ADR 0006](../../../docs/adr/0006-generation-and-consumption-are-separate.md)); nothing imports consumption.

## Acceptance criteria

- [x] `harness` is a registered console script; `harness --help` lists subcommands; unknown subcommand exits non-zero with a usage message.
- [x] `run_cli` executes a subcommand over **injected** ports (no env access in the core), returning an exit code and writing structured JSON to stdout; `main()` wires the real adapters from environment config and delegates to it.
- [x] `harness check-piece <run> <piece_id>` on a clean fixture Piece exits 0 with an empty violations list; on a doctored slop/invalid Piece it exits non-zero and lists the expected violation codes.
- [x] `harness check-constellation <run>` on the clean fixture run exits 0; a run with an injected invariant break (e.g. a dead end / missing cross-Topic Connection) exits non-zero and names the failing invariant.
- [x] `tests/harness/test_cli.py` drives `run_cli` in-process over the `fixture_run` substrate (`build_context`, `well_behaved_llm`, `InMemoryContentGraphRepository`) — asserting exit code + stdout + side-effects only, not re-testing the evaluators.
- [x] `ruff check`, `ruff format`, `mypy src`, `pytest` all pass; the CLI core is type-annotated with google-style docstrings.

## Blocked by

None — can start immediately.

## Completion

- Completed: 2026-07-07
- Commit: `f68d3ed4c9722231bf8ebf3a4857bb78039bd9a4`
