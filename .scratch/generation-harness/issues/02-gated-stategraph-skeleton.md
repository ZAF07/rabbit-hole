# Walking skeleton — the gated StateGraph runs end-to-end

Status: ready-for-agent
Feature: generation-harness
Blocked by: 01, content-graph/issues/01-03

## What to build

The pipeline's walking skeleton: the full staged DAG runs end-to-end on a **fixture Theme Brief** with all external access faked, producing a tiny constellation that the constellation evaluator certifies against Tier-1 I1–I8 — proving the DAG shape, the gate discipline, the ports, the manifest, and the outcome contract before any stage does real work.

- The uv project for the harness runtime and a **LangGraph `StateGraph`** with **fixed** stage order (0 Gate → 1 Plan → 2 Source → 3 Draft → 4 Edit → 5 Wire → 6 Constellation QA), the Stage-0 short-circuit, and a bounded QA loop — hand-built control flow, **not** a free-roaming supervisor.
- The **shared stage manifest** (data, not code): `stage → agent → deliverable → prerequisite → gate`, the single source of truth alongside the `harness/` markdown, consumable by both runtimes.
- **Ports** wired with fakes: `LLMPort` (fake), `WebSourcePort` (fake), and the `ContentGraphRepository` **in-memory fake imported from content-graph**.
- The **run-workspace writer** producing `runs/<id>/` (`plan.md`, `pieces/<id>/{sources.md,grounding.json,draft.md,piece.md}`, `connections.md`, `qa.md`) — where **the deliverable-on-disk IS the gate** (a stage refuses to start without its prerequisite artifact).
- **Stub agents** for all six stages that emit well-formed deliverables from the fake LLM.
- **Auto-approve gate hooks** at the three human-gate points (real gates land in issue 07); in the fixture run they auto-pass.
- Writes reach the Content Graph **only** as Pieces / Connections / Topic tags — never constellation, run id, Theme Brief, or grounding ledger ([ADR 0006](../../../docs/adr/0006-generation-and-consumption-are-separate.md)).

## Acceptance criteria

- [ ] End-to-end run over a fixture Brief with fake LLM + fake WebSource + in-memory ContentGraph writes a constellation that **passes I1–I8** (asserted via the issue-01 constellation evaluator).
- [ ] A stage **refuses to start** when its prerequisite deliverable is absent (gate discipline test).
- [ ] Stage 0 refuses to start Stage 1 unless DNA + a placeholder-free Brief exist.
- [ ] Only Pieces / Connections / Topic tags are written to the graph; a test asserts no generation-only field crosses.
- [ ] The stage manifest is data, read by the run; stage order is fixed.
- [ ] `ruff`, `mypy`, `pytest` pass.

## Blocked by

- generation-harness/issues/01 (guardrail evaluators — the constellation checker asserts the outcome)
- content-graph/issues/01-03 (the `ContentGraphRepository` port + in-memory fake covering Pieces, Topics, Connections)
