# Admin generation-trigger route — async, non-blocking, in-process

Status: completed
Feature: consumption-app
Blocked by: 06

## What to build

Let an operator kick off a content-generation run from the same backend, without a separate service and without stalling reader traffic ([ADR 0015](../../../docs/adr/0015-one-backend-deployable-http-api.md)). The generation pipeline itself already exists (`src/harness/`); this is the thin HTTP entry that mounts it.

- **Admin router** on the **same** FastAPI app from issue 06: a `POST` trigger that starts a generation run over the already-built `src/harness/` pipeline and **returns immediately** (`202` + a run handle). The run executes as an **in-process background task** — it never blocks the request or the reader endpoints.
- **Separate admin gate:** the trigger is guarded by a minimal operator auth (shared secret / basic), **distinct from reader identity**. An unauthenticated call is rejected.
- **Boundary held by imports:** the route calls the harness application entry, which reaches Postgres / LLM / web **only through its ports** (`ContentGraphRepository`, `LLMPort`, `WebSourcePort`). The **reader module imports no generation code, and generation imports no reader code** ([ADR 0006](../../../docs/adr/0006-generation-and-consumption-are-separate.md)).
- **(Minimal) status read-back:** an endpoint to check a triggered run's state, so the operator isn't blind after dispatch.

## Acceptance criteria

- [x] `POST` to the admin trigger starts a harness run and returns immediately (non-blocking); reader endpoints stay responsive while a run is in flight.
- [x] The run executes as a **background task in the same process** — no separate service, no separate deploy.
- [x] The admin route is gated **separately from reader identity**; an unauthenticated call is rejected.
- [x] An **import-boundary test** asserts the reader package imports no `harness` code and the `harness` package imports no reader code; the trigger touches the graph/LLM/web only through the existing ports.
- [x] A triggered run's state is queryable via a status endpoint.
- [x] `ruff`, `mypy`, `pytest` pass.

## Blocked by

- consumption-app/issues/06 (the FastAPI app / composition root the admin router mounts onto)

## Completion

- Completed: 2026-07-06
- Commit: `041c3cdcbbcfa94dc3503e9f1502c83ab3188676`

Evidence per criterion:

- Async 202 + readers responsive — `src/api/admin.py` `POST /admin/generation/runs` (`202`), dispatch off the request path via `src/api/generation.py` `GenerationService` (daemon-thread spawn); `tests/api/test_admin_api.py::test_the_trigger_is_non_blocking_and_readers_stay_responsive`.
- Background task in-process — `GenerationService._thread_spawn`; `::test_the_trigger_returns_before_the_run_executes`; real pipeline runs in-process in `tests/api/test_harness_trigger_integration.py`.
- Gate distinct from reader identity — `admin.py` `require_admin` (`X-Admin-Token`, `hmac.compare_digest`); `::test_the_trigger_requires_the_operator_secret`, `::test_a_reader_bearer_token_does_not_open_the_admin_route`.
- Import boundary + ports-only — `tests/api/test_import_boundary.py` (4 tests); `src/api/harness_runner.py` builds a `RunContext` from ports only, the single api module reaching `harness`.
- Status read-back — `GET /admin/generation/runs/{run_id}`; `::test_a_failed_run_is_reported_with_its_reason`, `::test_an_unknown_run_is_not_found`, integration test polls to `succeeded`.
- `ruff`/`mypy`/`pytest` — all pass (325 tests).
