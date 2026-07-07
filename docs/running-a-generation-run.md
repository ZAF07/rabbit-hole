# Running a generation run (human-gated, no UI)

How to drive a full content-generation run end-to-end from the command line —
including the three human approval gates — while there is no reader/admin UI yet.

The human review surface **is the run's file workspace** ([ADR 0013](adr/0013-human-review-surface-is-the-file-workspace.md)):
there is no separate approval screen by design. You review artifacts on disk,
record a verdict to an append-only log, and re-invoke the run to resume. This
doc is the operator playbook for that loop.

## The mental model

One command — `scripts/gen.py run <id>` — advances the pipeline to the **next
human gate and pauses**. You review the artifact(s) it produced, record an
**approve / reject** verdict, then run the same command again to **resume**. The
run continues off its on-disk deliverables, so re-invoking always picks up from
the first missing artifact.

There are **three gates**, fired in this order:

| Gate | Fires after | You review | Scope |
| --- | --- | --- | --- |
| **plan** | Stage 1 (Architect) | `plan.md` | whole run |
| **piece** | Stage 6 (QA) | `pieces/<id>/piece.md` | **once per Piece** |
| **constellation** | Stage 8 (re-QA) | `publish/connections.md` | whole run |

The full stage order is: 0 Gate → 1 Plan → 2 Source → 3 Draft → 4 Edit →
5 Wire → 6 QA → **[piece gate]** → 7 rewire → 8 re-QA →
**[constellation gate]** → 9 write ([ADR 0010](adr/0010-content-generation-pipeline-architecture.md),
[ADR 0012](adr/0012-publish-gate-rewire-and-reqa-approved-subset.md)).

## The driver: `scripts/gen.py`

A dev/operator tool that builds the same `RunContext` the API composition root
builds (Postgres Content Graph, the real DeepSeek adapter via `build_llm`,
Playwright web, and the real `WorkspaceVerdictGates`), but **pins the run id so
re-invoking resumes** the same workspace across gates. It uses only the
harness's public ports, so it never couples the reader path to generation
([ADR 0006](adr/0006-generation-and-consumption-are-separate.md),
[ADR 0016](adr/0016-production-llm-adapter-and-bounded-worker-agents.md)).

Two subcommands:

- `run <run_id> [--brief "..."]` — start or resume a run up to its next gate.
- `verdict <run_id> --gate <plan|piece|constellation> [--target <piece_id>] (--approve | --reject [--reason "..."])`
  — record a verdict.

## Preconditions

- **Docker Postgres up:** `docker compose up -d postgres` (listens on `localhost:5433`).
- **`.env` configured** with `DATABASE_URL`, and the generation keys
  `LLM_PROVIDER`, `LLM_API_KEY`, `LLM_MODEL_PRECISE`, `LLM_MODEL_CREATIVE`.
- **Extras installed:** `uv sync --extra llm --extra web` (plus Playwright
  browsers — `uv run playwright install chromium` if missing).
- **Topic taxonomy seeded** (one time, on a fresh DB) — the seed one-liner in
  [USAGE.md](../USAGE.md).

## The run, step by step

Throughout, `pressgang` is an example **run id** — any stable string; it becomes
the workspace directory name `harness/runs/pressgang/`.

### Step 1 — Kick it off (runs to the plan gate)

```bash
uv run python scripts/gen.py run pressgang --brief "How the printing press reshaped how knowledge spreads"
```

Writes `harness/runs/pressgang/goal.md`, runs Stage 0 (gate) → Stage 1
(Architect), preserves the machine draft as `plan.machine.md`, then pauses:

```
run pressgang: paused — awaiting verdict at gate: plan
```

`--brief` is required only on the **first** call (when `goal.md` doesn't exist
yet); omit it on every resume.

### Step 2 — The plan gate (whole run)

Read `harness/runs/pressgang/plan.md` — the Architect's constellation plan
(concepts, Topics, planned Connections). This is the highest-leverage gate; the
editorial moat lives here. Three moves:

- **Approve as-is:**
  ```bash
  uv run python scripts/gen.py verdict pressgang --gate plan --approve
  ```
- **Edit-then-approve:** edit `plan.md` in your editor, then run the same
  `--approve`. The driver computes the `plan.machine.md → plan.md` diff and
  records it as `edit_approve` automatically — that diff is the richest signal
  the Distiller learns from.
- **Reject:**
  ```bash
  uv run python scripts/gen.py verdict pressgang --gate plan --reject --reason "too broad; drop the telegraph tangent"
  ```
  A `--reason` is **required** on rejects.

### Step 3 — Resume to the per-piece gate

```bash
uv run python scripts/gen.py run pressgang
```

Resumes and runs Stage 2 Source (Researcher, grounded web) → 3 Draft (Writer) →
4 Edit (Editor + guardrails) → 5 Wire (Weaver) → 6 QA (Reviewer), then pauses at
the **piece gate**, which fires **once per Piece**:

```
run pressgang: paused — awaiting verdict at gate: piece <piece_id>
```

Review each `harness/runs/pressgang/pieces/<piece_id>/piece.md` (the run-root
`qa.md` holds the Reviewer's findings). Record a verdict **per piece** — note the
`--target`:

```bash
uv run python scripts/gen.py verdict pressgang --gate piece --target <piece_id> --approve
```

Approve/edit-approve the strong Pieces; reject the weak ones with a reason.
Rejected Pieces drop out of the published set; the rest carry forward. Re-run
`run` after each verdict, or verdict them all and re-run once — it re-pauses
until **every** Piece has a verdict.

### Step 4 — Resume to the constellation gate

```bash
uv run python scripts/gen.py run pressgang
```

Runs the publish-side Stage 7 rewire (Weaver over the survivors) → 8 re-QA
(graph invariants over survivors), then pauses at the **constellation gate**.
Review `harness/runs/pressgang/publish/connections.md` — the final wiring over
the approved subset, guaranteed no dead ends:

```bash
uv run python scripts/gen.py verdict pressgang --gate constellation --approve
```

### Step 5 — Final resume writes to the Content Graph

```bash
uv run python scripts/gen.py run pressgang
```

Stage 9 (write) does the atomic insert of the re-validated survivor set into
Postgres and drops `publish/published.json`. The run ends `succeeded`. `/daily`
can now serve it (once a Daily Feature is assigned).

## Artifacts a run leaves behind

Under `harness/runs/<run_id>/`:

- `goal.md` — the brief you seeded.
- `plan.md` (+ `plan.machine.md`) — the Architect's plan and its preserved machine draft.
- `pieces/<id>/` — `sources.md`, `grounding.json`, `draft.md`, `piece.md` (+ `piece.machine.md`).
- `connections.md`, `qa.md` — wiring and QA.
- `publish/connections.md`, `publish/qa.md`, `publish/published.json` — the publish-side artifacts.
- `feedback/verdicts.jsonl` — every verdict you recorded, stamped with the real DeepSeek model id (what the Distiller learns from).
- `usage.json` — per-run model calls and token spend, aggregated per tier.

## Two things worth knowing

- **`run` is idempotent and doubles as a status check.** Re-running before
  you've recorded the pending verdict just re-pauses at the same gate — cheap,
  since completed stages skip on their existing deliverables. It only advances
  once the gate it's waiting on has a verdict.
- **Why not the HTTP admin trigger for this?** `POST /admin/generation/runs`
  mints a new run id on every call and has **no resume-by-id**, and it reports a
  *paused* run as `succeeded`. It's the right tool for an unattended /
  auto-approve run or a first-leg kick-off, but a human-in-the-loop run needs
  the in-process driver so the same workspace is resumed across all three gates.

## Verdict semantics (reference)

Recorded to `feedback/verdicts.jsonl`; the **latest** verdict for a target wins.

- `approve` — accept the machine draft unchanged.
- `edit_approve` — inferred automatically when you edited the working copy
  before approving; the unified machine→human diff is attached.
- `reject` — requires a reason; the target drops from the published set and the
  reason feeds the Distiller.
