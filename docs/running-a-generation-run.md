# Running a generation run (human-gated, no UI)

How to drive a full content-generation run end-to-end from the command line —
including the three human approval gates — while there is no reader/admin UI yet.

The human review surface **is the run's file workspace** ([ADR 0013](adr/0013-human-review-surface-is-the-file-workspace.md)):
there is no separate approval screen by design. You review artifacts on disk,
record a verdict to an append-only log, and re-invoke the run to resume. This
doc is the operator playbook for that loop.

## The mental model

One command — `harness run <id>` — advances the pipeline to the **next
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

## The driver: the `harness` CLI

The first-class `harness` console script (`src/harness/cli.py`) is the shared
deterministic seam both this in-process driver and the `/new-constellation`
Claude Code runtime call ([ADR 0019](adr/0019-claude-code-generation-runtime-and-shared-harness-cli.md)).
Its `main()` builds the same `RunContext` the API composition root builds
(Postgres Content Graph, the real DeepSeek adapter via `build_llm`, Playwright
web, and the real `WorkspaceVerdictGates`), but **pins the run id so re-invoking
resumes** the same workspace across gates. It uses only the harness's public
ports, so it never couples the reader path to generation
([ADR 0006](adr/0006-generation-and-consumption-are-separate.md),
[ADR 0016](adr/0016-production-llm-adapter-and-bounded-worker-agents.md)).

The subcommands this playbook uses:

- `run <run_id> [--brief "..."]` — start or resume a run up to its next gate.
- `verdict <run_id> --gate <plan|piece|constellation> [--target <piece_id>] (--approve | --reject [--reason "..."])`
  — record a verdict.
- `status <run_id>` — report where the run is paused, read-only.
- `publish <run_id>` — re-wire, re-QA, and atomically write the approved
  survivors (the `run` command's final resume does this for you; run it by hand
  only to publish a run you walked with the Claude runtime).

The same CLI also exposes `check-piece` / `check-constellation` (the binary
Tier-1 guardrails) and `fetch` (the recall-first web port); the interactive
`/new-constellation` runtime drives those directly (see below).

## Two ways to drive a run

There are two runtimes over this one CLI, and they never share an execution path
— only the manifest, the specs, and the run workspace ([ADR 0019](adr/0019-claude-code-generation-runtime-and-shared-harness-cli.md)):

- **In-process driver (`harness run`)** — you are the model of nothing; the
  production DeepSeek/LangGraph pipeline authors every stage and you only review
  at the gates. This is the loop the rest of this doc walks. Use it to drive the
  production engine by hand across the three gates.
- **Claude Code runtime (`/new-constellation`)** — Claude Code is the *conductor*
  and the *author*: it walks the same manifest, delegates each stage to the
  subagent cards, and grounds/checks/writes through this same CLI, so its output
  is held to the identical contract. Use it to author a constellation
  interactively with Claude as the model. DeepSeek is not called on this path.

Both write `harness/runs/<id>/` with the same artifact layout, preserve the same
`*.machine.md` copies, pause at the same three gates, and publish through the
same write port — so a run is even resumable across engines (though a single run
should stay on one for coherence).

### The `/new-constellation` runtime

`/new-constellation <theme brief>` (`.claude/skills/new-constellation/SKILL.md`)
makes Claude Code conduct one run end-to-end. The skill is a thin conductor: at
run start it **reads `harness/manifest.toml` and the agent cards**, then walks
stages in manifest order under the deliverable-on-disk prerequisite gate — the
pipeline is never written down twice. Claude does the creative and judgment work
(plan, recall + source, draft, anti-slop revision, hooks, Tier-2 coherence); the
CLI does the binary work:

- the **Researcher** grounds via `harness fetch <url>` — the recall-first
  `WebSourcePort`, raw text + outlinks, no search engine ([ADR 0011](adr/0011-harness-tools-are-ports-web-sourcing-recall-first.md));
  Claude Code's own `WebSearch`/`WebFetch` are **not** used for grounding.
- the **Editor** revises each Piece against `harness check-piece <id> <piece>`
  until it exits `0`.
- the **Reviewer** asserts Tier-1 I1–I8 via `harness check-constellation <id>`.

At each of the three human gates it presents the artifact plus the relevant
`check-*` report, takes your decision in-session, records it via
`harness verdict`, and resumes; it publishes via `harness publish`. The
subagents call the CLI through a real `Bash` grant scoped to `harness` — the
`tools:` grants on `researcher.md` / `editor.md` / `reviewer.md`, regenerated
from `harness/agents/README.md`.

**Full operator how-to:** [new-constellation-guide.md](new-constellation-guide.md)
— preconditions, the structured `goal.md` Theme Brief (front-matter with
`target_topics` as **exact seeded Topic slugs**), the seeded-slug reference, and
troubleshooting. That is the doc to follow when driving the Claude runtime; the
rest of *this* page is the DeepSeek/LangGraph engine.

Because Claude is forced through the identical `check-*` gates and the identical
write, it cannot publish an out-of-contract constellation any more than the
LangGraph runtime can: **same pipeline, same contract, same write — not
identical prose** (a different model writes it). Stage 0 stops the skill loud on
a placeholder or empty brief before any stage runs.

## Driving the production engine by hand (`harness run`)

## Preconditions

- **Docker Postgres up:** `docker compose up -d postgres` (listens on `localhost:5433`).
- **`.env` configured** with `DATABASE_URL`, and the generation keys
  `LLM_PROVIDER`, `LLM_API_KEY`, `LLM_MODEL_PRECISE`, `LLM_MODEL_CREATIVE`.
- **Extras installed:** `uv sync --extra llm --extra web` (plus Playwright
  browsers — `uv run playwright install chromium` if missing).
- **Topic taxonomy seeded** (one time, on a fresh DB) — the seed one-liner in
  [USAGE.md](../USAGE.md).

## The run, step by step

Throughout, `invisible-systems` is an example **run id** — any stable string; it
becomes the workspace directory name `harness/runs/invisible-systems/`. This
walkthrough drives the **same** worked example as the Claude runtime
([new-constellation-guide.md](new-constellation-guide.md)) — one brief, two
drivers — so you can compare the engines on identical input.

### Step 1 — Author the brief, then kick it off (runs to the plan gate)

The run's input, `goal.md`, is a **structured Theme Brief** (front-matter), not a
sentence: it needs `through_line`, `target_topics` (as **exact seeded Topic
slugs**), and `piece_count`. See the brief format + the seeded-slug reference in
[new-constellation-guide.md](new-constellation-guide.md) §2. Write it into the
workspace, then start the run:

```bash
mkdir -p harness/runs/invisible-systems
cat > harness/runs/invisible-systems/goal.md <<'EOF'
---
through_line: >
  The invisible systems that move the physical world — a ship, a chip, a
  ledger, a strait — and how one failure in any of them cascades into all
  the others.
target_topics:
  - logistics-and-supply-chains
  - semiconductors
  - financial-systems
  - chokepoints-and-geography
piece_count: 4
---
EOF

uv run harness run invisible-systems
```

Runs Stage 0 (gate) → Stage 1 (Architect), preserves the machine draft as
`plan.machine.md`, then pauses:

```
run invisible-systems: paused — awaiting verdict at gate: plan
```

The `run` command can instead seed `goal.md` for you via `--brief` on the first
call, but `--brief` writes its argument to `goal.md` **verbatim** — so it must be
the whole front-matter document, not a one-line theme. Authoring the file (above)
is clearer. Either way, omit any brief on every **resume** — the run reads the
`goal.md` already on disk.

### Step 2 — The plan gate (whole run)

Read `harness/runs/invisible-systems/plan.md` — the Architect's constellation plan
(concepts, Topics, planned Connections). This is the highest-leverage gate; the
editorial moat lives here. Three moves:

- **Approve as-is:**
  ```bash
  uv run harness verdict invisible-systems --gate plan --approve
  ```
- **Edit-then-approve:** edit `plan.md` in your editor, then run the same
  `--approve`. The driver computes the `plan.machine.md → plan.md` diff and
  records it as `edit_approve` automatically — that diff is the richest signal
  the Distiller learns from.
- **Reject:**
  ```bash
  uv run harness verdict invisible-systems --gate plan --reject --reason "too broad; drop the telegraph tangent"
  ```
  A `--reason` is **required** on rejects.

### Step 3 — Resume to the per-piece gate

```bash
uv run harness run invisible-systems
```

Resumes and runs Stage 2 Source (Researcher, grounded web) → 3 Draft (Writer) →
4 Edit (Editor + guardrails) → 5 Wire (Weaver) → 6 QA (Reviewer), then pauses at
the **piece gate**, which fires **once per Piece**:

```
run invisible-systems: paused — awaiting verdict at gate: piece <piece_id>
```

Review each `harness/runs/invisible-systems/pieces/<piece_id>/piece.md` (the run-root
`qa.md` holds the Reviewer's findings). Record a verdict **per piece** — note the
`--target`:

```bash
uv run harness verdict invisible-systems --gate piece --target <piece_id> --approve
```

Approve/edit-approve the strong Pieces; reject the weak ones with a reason.
Rejected Pieces drop out of the published set; the rest carry forward. Re-run
`run` after each verdict, or verdict them all and re-run once — it re-pauses
until **every** Piece has a verdict.

### Step 4 — Resume to the constellation gate

```bash
uv run harness run invisible-systems
```

Runs the publish-side Stage 7 rewire (Weaver over the survivors) → 8 re-QA
(graph invariants over survivors), then pauses at the **constellation gate**.
Review `harness/runs/invisible-systems/publish/connections.md` — the final wiring over
the approved subset, guaranteed no dead ends:

```bash
uv run harness verdict invisible-systems --gate constellation --approve
```

### Step 5 — Final resume writes to the Content Graph

```bash
uv run harness run invisible-systems
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
