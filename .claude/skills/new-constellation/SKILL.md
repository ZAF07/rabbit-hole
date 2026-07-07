---
name: new-constellation
description: Conduct one full content-generation run as the Claude Code runtime — walk harness/manifest.toml stage by stage, delegate each stage to its subagent, fire the three human gates, and publish through the shared `harness` CLI. Invoke as `/new-constellation <run id>`, where the operator has already authored the run's structured goal.md Theme Brief.
---

# /new-constellation — conduct a generation run

You are the **conductor** of one Rabbit Hole generation run ([ADR 0019](../../../docs/adr/0019-claude-code-generation-runtime-and-shared-harness-cli.md)). Claude Code is the *second real runtime* alongside production DeepSeek/LangGraph: **you do the creative and judgment work; the shared `harness` CLI enforces the binary contract and does the write.** Parity with production is by construction — you walk the same `harness/manifest.toml`, honor the same specs, and are forced through the same `check-*` gates and the same atomic write. You never call DeepSeek, and you never restate the pipeline: the manifest is the single source of truth, so you **read it at run start** and follow it.

Respect the [ADR 0006](../../../docs/adr/0006-generation-and-consumption-are-separate.md) boundary: this run writes only Pieces, Connections, and Topic tags. It knows nothing about users, sessions, or the reader app.

## Argument

`/new-constellation <run id>` — the argument names the run and its workspace `harness/runs/<run_id>/` (kebab-case, e.g. `invisible-systems`). Re-invoking with the same id **resumes** — every stage skips work whose deliverable already exists, so you always pick up from the first missing artifact.

The run's input is a **hand-authored Theme Brief** at `harness/runs/<run_id>/goal.md` — structured front-matter (`through_line`, `target_topics` as **exact seeded Topic slugs**, `piece_count`, plus optional fields), *not* a sentence. The operator writes it before invoking you (see [`docs/new-constellation-guide.md`](../../../docs/new-constellation-guide.md)). **You never invent the brief or its `target_topics`** — the topics must be real rows in the Content Graph or the publish write fails with `TopicNotFoundError`. If `goal.md` is absent, stop and tell the operator to author it (per that guide) before you run anything.

## Preconditions (fail loud if unmet)

The `harness` CLI must be runnable and its ports wired the same way the operator playbook describes (`docs/running-a-generation-run.md`): Docker Postgres up, `.env` with `DATABASE_URL` + the generation keys, `uv sync --extra llm --extra web`, taxonomy seeded. You drive everything through `uv run harness …` — never touch Postgres, the LLM, or Playwright directly.

## Stage 0 — the gate (stop loud on failure)

Before any stage runs, verify the run can legitimately start:

1. The **Editorial DNA** (`harness/editorial/dna.md`) and the active **Voice Profile** (`harness/editorial/voices/`) are present and non-empty.
2. A hand-authored **Theme Brief** exists at `harness/runs/<run_id>/goal.md`. If it is **missing**, stop and tell the operator to author it (structured front-matter with `target_topics` chosen from the seeded Topic slugs — see [`docs/new-constellation-guide.md`](../../../docs/new-constellation-guide.md)); **do not fabricate one.** If it exists but is empty or holds a placeholder (`<...>`, `TODO`, `TBD`, lorem ipsum), **stop here and report why** — do not run a single stage.

The brief is already on disk (the operator wrote it); you do not seed it. The manifest's Stage 0 gate ("Editorial DNA + Theme Brief present, no unfilled placeholders") is the same check the production runtime applies — it also validates that the front-matter parses (`through_line`, `target_topics`, `piece_count` present).

## Walk the manifest (do not hard-code the stages)

**At run start, read [`harness/manifest.toml`](../../../harness/manifest.toml) and the agent cards in [`harness/agents/README.md`](../../../harness/agents/README.md).** The manifest — not this file — is the authoritative stage list, prerequisite set, and gate placement. Walk `[[stages]]` in `number` order and honor the rule the manifest states: **the deliverable-on-disk IS the gate** — a stage cannot start until *every* prerequisite artifact exists (all `{piece_id}` expansions for once-stages), and a stage whose deliverable already exists is skipped. If the manifest changes, follow the new manifest; never trust the summary below over the file you just read.

For each stage, delegate to the subagent the manifest names in its `agent` field, giving it the stage's `Reads`/`Produces`/`Task`/`Done when` from its card. The creative shape (per ADR 0019, today's manifest):

| Stage | Subagent | You do | The seam does |
| --- | --- | --- | --- |
| 1 plan | **architect** | design the constellation plan → `plan.md` | — |
| 2 source | **researcher** | recall candidate URLs, then **`harness fetch <url>`** to fetch raw text + outlinks and citation-chase to primaries → `sources.md` + `grounding.json` | recall-first web port (ADR 0011) |
| 3 draft | **writer** | closed-book narrative from the vetted pack only → `draft.md` | — |
| 4 edit | **editor** | anti-slop / voice pass, then revise against **`harness check-piece <run_id> <piece_id>`** until it passes → `piece.md` | binary piece guardrails |
| 5 wire | **weaver** | write every Connection's per-origin hook → `connections.md` | — |
| 6 qa | **reviewer** | judge Tier-2 coherence; assert Tier-1 via **`harness check-constellation <run_id>`** → `qa.md` | binary invariants I1–I8 |

**Grounding is closed-book and recall-first (ADR 0011):** the Researcher grounds **only** through `harness fetch`. Do **not** use Claude Code's `WebSearch` (a search engine, forbidden in V1) or `WebFetch` (it summarizes instead of returning raw text + outlinks, breaking closed-book fidelity) for grounding.

**The check commands are the contract, not advice.** `check-piece` exits non-zero with a `violations` array while a Piece still trips the guardrails; loop the Editor until it exits `0`. `check-constellation` exits non-zero with `failed` invariant codes until Tier-1 holds; do not carry a Piece past QA that fails its check.

## The three human gates

The manifest's `[[human_gates]]` declare where you pause: **plan** (after stage 1, whole run), **piece** (after stage 6, once per Piece), **constellation** (after the publish-side re-QA, whole run). At each gate:

1. Present the artifact the gate targets (`plan.md`, each `pieces/<id>/piece.md`, or `publish/connections.md`) **plus** the relevant `harness check-*` report, so the human decides with the contract result in hand.
2. Take the human's **approve / reject** decision in-session. If they edit the working copy before approving, that edit is the signal — the CLI infers `edit_approve` from the `*.machine.md → *.md` diff automatically; you never pass it.
3. Record it through the seam:
   - Plan / constellation: `uv run harness verdict <run_id> --gate <plan|constellation> (--approve | --reject --reason "…")`
   - Each Piece: `uv run harness verdict <run_id> --gate piece --target <piece_id> (--approve | --reject --reason "…")`

   A **reject requires `--reason`** (it feeds the Distiller). Rejected Pieces drop from the published set; the survivors carry forward.

## Run it — you conduct; the seam checks, records, and writes

This path **does not use `harness run`** — that command is the *other* runtime (it makes DeepSeek/LangGraph author every stage). Here you author by delegating to subagents, own the workspace files, and call the CLI only for the parts that must be identical to production: `fetch`, `check-*`, `verdict`, `publish`. Use `uv run harness status <run_id>` any time to see which gate is pending (read-only).

**Stamp the run as the Claude runtime first.** Verdicts carry a `runtime` + `model` identity so the Distiller ([ADR 0004](../../../docs/adr/0004-human-ratified-learning-loop.md)) can tell the two engines apart ([ADR 0019](../../../docs/adr/0019-claude-code-generation-runtime-and-shared-harness-cli.md) decision 6). The CLI defaults that identity to `langgraph` + the DeepSeek model, so **export it for the session before any `harness verdict`** — otherwise a Claude-authored run is mis-stamped as production:

```
export HARNESS_RUNTIME=claude-code
export HARNESS_MODEL=<the model you are running as>
```

You own the workspace's on-disk artifacts. A clean way to do that: each subagent **returns its deliverable's content**; you write it to the workspace path the manifest names. That keeps file I/O in your hands (so a subagent's tool grant only needs to cover its CLI calls) and lets you preserve the machine copy uniformly. The `researcher`, `editor`, and `reviewer` call the CLI themselves via their `Bash` grant during their loop; the rest return content you place.

1. **Stage 0.** Run the Stage-0 gate above against the operator-authored `harness/runs/<run_id>/goal.md` (you do not write it). If it passes, proceed. (On a resume the workspace already has deliverables — skip straight to the first missing one.)
2. **Stage 1 — plan.** Delegate to `architect`; write its plan to `plan.md`. **Preserve the machine copy** before the human can touch it: `cp harness/runs/<run_id>/plan.md harness/runs/<run_id>/plan.machine.md`.
3. **Plan gate.** Present `plan.md`. The human approves as-is, edits-then-approves (leave their edits in `plan.md` — the CLI infers `edit_approve` from the `plan.machine.md → plan.md` diff), or rejects:
   `uv run harness verdict <run_id> --gate plan (--approve | --reject --reason "…")`
4. **Stages 2–6, per the manifest.** For each planned Piece: `researcher` (grounds via `harness fetch`) → `sources.md` + `grounding.json`; `writer` → `draft.md`; `editor` (loops on `harness check-piece <run_id> <piece_id>` until exit `0`) → `piece.md`, then `cp …/piece.md …/piece.machine.md`. Once every Piece exists: `weaver` → `connections.md`; `reviewer` (asserts `harness check-constellation <run_id>` exits `0`) → `qa.md`.
5. **Piece gates (once per Piece).** Present each `pieces/<id>/piece.md` with its `check-piece` report:
   `uv run harness verdict <run_id> --gate piece --target <piece_id> (--approve | --reject --reason "…")`
   Rejected Pieces drop from the published set; survivors carry forward.
6. **Constellation gate, then publish.** Present the wired constellation (`connections.md` + the `check-constellation` report) for the final decision, and record it:
   `uv run harness verdict <run_id> --gate constellation (--approve | --reject --reason "…")`
   Then do the write: `uv run harness publish <run_id>`. Publish re-wires and re-QAs the approved survivors and **atomically writes only the re-validated set** to the Content Graph through the same write port production uses — exit `0` means the whole survivor set published; a non-zero exit lists any Piece flagged back (only the valid set was written). Publish **enforces the constellation gate itself** — with no approving verdict it re-wires, leaves `publish/connections.md` for review, and exits `2` (`awaiting verdict`) **without writing**; a rejected gate also blocks the write. So the final gate is a property of the seam, not of your diligence: record the approve first (or after publish pauses), then re-run `publish` to write.

The published survivors are now in the Content Graph — indistinguishable to the reader surface from a DeepSeek-made one, because they went through the identical contract and the identical write.

## Guardrails on you, the conductor

- **Never** bypass a `check-*` failure by editing the artifact to hide it, or publish a constellation whose `check-constellation` did not exit `0`.
- **Never** ground outside `harness fetch`; **never** invent facts the claim pack doesn't hold (closed-book).
- **Never** import or read consumption/user/session concerns — this run is generation-only.
- If a stage fails loud (thin source pack, unsatisfiable plan, escalated Piece), **stop and surface it** rather than papering over — the harness is built to fail early, not to ship slop.
