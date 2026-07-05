---
name: verify
description: How to verify harness/content-graph changes in the running system (real Postgres + real run workspace). Use when /verify needs a handle on this repo.
---

# Verifying rabbit-hole in the running system

The generation harness is a library; its surface is the package boundary
(`harness.pipeline.graph.run_pipeline`, `harness.review.surface.record_verdict`,
`harness.runtimes.manifest_runner.run_manifest_pipeline`) plus the Content
Graph in Postgres. There is no CLI yet. Verify by driving a real run the way
the V1 operator would.

## Handle

- Postgres: `docker compose up -d postgres` → `rabbit-hole-postgres` on
  `localhost:5433` (user/pass/db: `rabbit`/`rabbit`/`content_graph`).
- Create a scratch DB (e.g. `content_graph_verify`), migrate with
  `content_graph.adapters.migrate.apply_migrations(conn)`, wire
  `PostgresContentGraphRepository(conn)` into the `RunContext`.
- Real specs: `SpecLibrary(repo_root=<repo>)` reads `harness/editorial/`,
  `harness/guardrails/`, `harness/manifest.toml`, `docs/taxonomy.md`.
- Workspace: `RunWorkspace(<repo>/harness/runs/<run-id>)` — gitignored, and
  inspecting it after a run is itself part of verification (plan.md,
  `*.machine.md` copies, `pieces/<id>/…`, `feedback/verdicts.jsonl`).
- LLM/web ports: no production LLM adapter exists yet — use the scripted
  handlers from `tests.harness.fixture_run` (`well_behaved_llm()`,
  `fixture_web_source()`, `FIXTURE_GOAL`) with `PYTHONPATH` at repo root.

## Drive

1. `run_pipeline(ctx)` → pauses at gate: plan.
2. Edit `plan.md` by hand, `record_verdict(..., "approve", ...)` → expect
   `edit_approve` with a unified diff.
3. Re-invoke; approve/reject each Piece at its pause (reject needs a reason).
4. Re-invoke; approve `constellation`; re-invoke → `completed`.
5. Check rows with SQL: `pieces`, `connections`, `topics` — rejected Piece
   absent, survivor ring intact.

## Probes that proved sharp

- Re-invoke after completion → idempotent re-publish, same state.
- Second run against the same DB → Architect dedup raises
  `ContractViolationError` (real SQL read path).
- `record_verdict(..., "reject")` with no reason → `MalformedArtifactError`.
- `PlaywrightWebSource().fetch(...)` without the `web` extra → RuntimeError
  naming `uv sync --extra web`.
- `distill(read_verdicts(ws), guardrail_text)` then `render_proposal` →
  guardrail file must be byte-identical afterward.
