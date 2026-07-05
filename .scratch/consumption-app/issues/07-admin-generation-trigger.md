# Admin generation-trigger route — async, non-blocking, in-process

Status: ready-for-agent
Feature: consumption-app
Blocked by: 06

## What to build

Let an operator kick off a content-generation run from the same backend, without a separate service and without stalling reader traffic ([ADR 0015](../../../docs/adr/0015-one-backend-deployable-http-api.md)). The generation pipeline itself already exists (`src/harness/`); this is the thin HTTP entry that mounts it.

- **Admin router** on the **same** FastAPI app from issue 06: a `POST` trigger that starts a generation run over the already-built `src/harness/` pipeline and **returns immediately** (`202` + a run handle). The run executes as an **in-process background task** — it never blocks the request or the reader endpoints.
- **Separate admin gate:** the trigger is guarded by a minimal operator auth (shared secret / basic), **distinct from reader identity**. An unauthenticated call is rejected.
- **Boundary held by imports:** the route calls the harness application entry, which reaches Postgres / LLM / web **only through its ports** (`ContentGraphRepository`, `LLMPort`, `WebSourcePort`). The **reader module imports no generation code, and generation imports no reader code** ([ADR 0006](../../../docs/adr/0006-generation-and-consumption-are-separate.md)).
- **(Minimal) status read-back:** an endpoint to check a triggered run's state, so the operator isn't blind after dispatch.

## Acceptance criteria

- [ ] `POST` to the admin trigger starts a harness run and returns immediately (non-blocking); reader endpoints stay responsive while a run is in flight.
- [ ] The run executes as a **background task in the same process** — no separate service, no separate deploy.
- [ ] The admin route is gated **separately from reader identity**; an unauthenticated call is rejected.
- [ ] An **import-boundary test** asserts the reader package imports no `harness` code and the `harness` package imports no reader code; the trigger touches the graph/LLM/web only through the existing ports.
- [ ] A triggered run's state is queryable via a status endpoint.
- [ ] `ruff`, `mypy`, `pytest` pass.

## Blocked by

- consumption-app/issues/06 (the FastAPI app / composition root the admin router mounts onto)
