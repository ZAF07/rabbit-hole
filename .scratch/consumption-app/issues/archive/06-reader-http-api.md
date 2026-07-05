# Reader HTTP API — the FastAPI app, response DTOs, anonymous identity

Status: completed
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

- [x] One FastAPI app (`src/api/`) exposes all six reader use-cases as HTTP endpoints, driven through the app-service boundary.
- [x] First contact mints an anonymous `user_id` + token; a subsequent request bearing it is attributed to that user and its path persists per that identity.
- [x] Response DTOs carry only Pieces/Connections/Topics fields; a test asserts **no `run_id` / constellation** reaches the wire.
- [x] API responses use **internal vocabulary only**; a test asserts the API emits no branded string (those live only in the presentation vocab module).
- [x] The full loop is exercised **end-to-end over HTTP** against the in-memory fakes: daily feature → read → pull → backtrack → resume → tapestry.
- [x] `ruff`, `mypy`, `pytest` pass.

## Blocked by

- consumption-app/issues/04 (all six reader use-cases + read models exist to expose; 05 supplies the real Postgres store the same app runs against by config)

## Completion

- Completed: 2026-07-06
- Commit: `041c3cdcbbcfa94dc3503e9f1502c83ab3188676`

Evidence per criterion:

- Six use-cases on the wire — `src/api/reader.py` `build_reader_router`: `GET /daily`, `POST /pieces/{id}/read` (ReadPiece → guarded `enter_piece`), `POST /pull`, `POST /backtrack`, `GET /resume`, `GET /knowledge-graph`, all through `ReaderService`.
- Identity mint + attribution — `src/api/dependencies.py` `current_user_id`; `tests/api/test_reader_api.py::test_first_contact_mints_a_token...`, `::test_a_bearer_token_attributes_later_requests_to_the_same_reader`.
- No `run_id`/constellation on the wire — `tests/api/test_reader_api.py::test_no_generation_only_field_reaches_the_wire`.
- No branded string — `::test_no_branded_string_reaches_the_wire` (walks `VOCABULARY`).
- Full loop e2e over HTTP — `::test_the_full_loop_runs_end_to_end_over_http`; also verified in a live uvicorn server over TCP.
- `ruff`/`mypy`/`pytest` — all pass (325 tests).
