# Reader HTTP API — the FastAPI app, response DTOs, anonymous identity

Status: ready-for-agent
Feature: consumption-app
Blocked by: 04

## What to build

Put the reader use-cases on the wire so a real client (mobile + web) can drive the core loop over HTTP — the missing slice the PRD implied by "its API" but never issued ([ADR 0015](../../../docs/adr/0015-one-backend-deployable-http-api.md)).

- **The composition root — `src/api/`:** **one FastAPI app** that wires the `consumption` use-cases over their ports. This same app later mounts the admin generation router (issue 07); it is the single backend deployable.
- **Reader router:** HTTP endpoints over the six use-cases — `GetDailyFeature`, `ReadPiece`, `PullConnection`, `Backtrack`, `ResumeSession`, `GetTapestry`.
- **Response DTOs:** serialize the app-service read models to JSON exposing **only Pieces/Connections/Topics fields**. The wire format carries **internal vocabulary only** — branded strings ("Thread", "Tapestry") render **client-side** from the presentation vocabulary module ([ADR 0001](../../../docs/adr/0001-decouple-internal-and-ui-vocabulary.md)); the API never emits them, and never emits `run_id` / constellation ([ADR 0006](../../../docs/adr/0006-generation-and-consumption-are-separate.md)).
- **Anonymous identity at the edge:** on first contact the API **mints an opaque `user_id` + token** (via the issue-02 `UserRepository`); subsequent requests carry the token and are attributed to that user, keying their path + Tapestry. **No login / email / accounts** in V1.
- Runs over the **in-memory fakes** in tests (httpx / TestClient); the real Postgres adapters arrive in issue 05 — the API is store-agnostic (selected by config).

## Acceptance criteria

- [ ] One FastAPI app (`src/api/`) exposes all six reader use-cases as HTTP endpoints, driven through the app-service boundary.
- [ ] First contact mints an anonymous `user_id` + token; a subsequent request bearing it is attributed to that user and its path persists per that identity.
- [ ] Response DTOs carry only Pieces/Connections/Topics fields; a test asserts **no `run_id` / constellation** reaches the wire.
- [ ] API responses use **internal vocabulary only**; a test asserts the API emits no branded string (those live only in the presentation vocab module).
- [ ] The full loop is exercised **end-to-end over HTTP** against the in-memory fakes: daily feature → read → pull → backtrack → resume → tapestry.
- [ ] `ruff`, `mypy`, `pytest` pass.

## Blocked by

- consumption-app/issues/04 (all six reader use-cases + read models exist to expose; 05 supplies the real Postgres store the same app runs against by config)
