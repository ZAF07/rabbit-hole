# Collapse the two Postgres stores into one database (single DATABASE_URL)

Status: completed

## Context

The system is two _code_ subsystems joined only by the Content Graph port
([ADR 0006](../../../docs/adr/0006-generation-and-consumption-are-separate.md)):
generation writes Pieces/Topics/Connections; consumption reads them and owns the
reader's user/session/journey tables. That code boundary is correct and stays.

But nothing in the code requires **two physical databases** — the appearance of
two came only from two independent DSN env vars (`CONTENT_GRAPH_DSN`,
`CONSUMPTION_DSN`), so the docs stood up two DBs to fill them. The content tables
and reader tables have disjoint names, and both migration runners record into
`schema_migrations` keyed by distinct filenames, so one database holds all of it
with no collision. Two databases is needless operator ceremony.

## Decisions (grilled)

- One database, addressed by a single `DATABASE_URL` env var read by both
  `ContentGraphConfig` and `ConsumptionConfig` (the two typed Config classes stay
  — module boundary untouched; they just resolve the same DSN).
- Boot auto-migrates **both** schemas (`build_app_from_env`), so cold start is
  `createdb` -> run app. Taxonomy seeding stays a manual one-liner (it's content
  data, not schema).
- Out of scope: the `*_TEST_DSN` contract-test databases — test isolation is
  orthogonal to production topology.

## Acceptance criteria

- [x] Both config classes read `DATABASE_URL`; `CONTENT_GRAPH_DSN` /
      `CONSUMPTION_DSN` are gone from code, `.env.example`, and docs.
- [x] `build_app_from_env` applies content-graph + consumption migrations on boot
      against the one database, then serves.
- [x] `docker-compose.yml`, `.env.example`, and `USAGE.md` describe one database;
      USAGE cold-start drops the `createdb consumption` step and the manual
      content-graph migrate one-liner.
- [x] An ADR records the topology decision (one DB; logical, not physical,
      separation) and its tradeoff.
- [x] Quality gates pass: `uv run ruff check .`, `uv run ruff format`,
      `uv run mypy src`, `uv run pytest`.

## Completion

- Completed: 2026-07-07
- Commit: `f32c1b011df4b8925615722b58b48fe343f08f69`
