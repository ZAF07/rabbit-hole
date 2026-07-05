# Agent Roster

The seven agents of the content-generation harness. Each is a **single-responsibility specialist** with one deliverable. Following the we-os pattern, **the prerequisite deliverable existing on disk *is* the gate** for the next stage — no deliverable, no progress.

This file is the design-time home for all specs. At build time each spec section splits into its own `.claude/agents/<name>.md` (Claude Code subagent) and is the same markdown the LangGraph node reads — **one spec, two runtimes** (dual-runtime parity).

## Spec-card contract
Every agent spec is a card with these fields:

- **Stage / fan-out** — pipeline stage; whether it runs once or maps per Piece.
- **Reads** — required inputs (files that must exist).
- **Produces** — the *single* deliverable (path).
- **Tools** — external ports the agent may call (`WebSourcePort`, `ContentGraphRepository`); most agents have none and are pure file-in / file-out ([ADR 0011](../../docs/adr/0011-harness-tools-are-ports-web-sourcing-recall-first.md)).
- **Honors** — the guardrail / DNA files it must obey.
- **Task** — the ordered procedure.
- **Done when** — the output contract that makes the deliverable a valid gate.

## Roster at a glance

| # | Agent | Stage | Fan-out | Deliverable |
| --- | --- | --- | --- | --- |
| 1 | Architect | 1 · Plan | once | `plan.md` |
| 2 | Researcher | 2 · Source | per Piece | `pieces/<id>/sources.md` + `grounding.json` |
| 3 | Writer | 3 · Draft | per Piece | `pieces/<id>/draft.md` |
| 4 | Editor | 4 · Edit | per Piece | `pieces/<id>/piece.md` |
| 5 | Weaver | 5 · Wire | once | `connections.md` |
| 6 | Reviewer | 6 · Constellation QA | once | `qa.md` |
| 7 | Distiller | learning loop | batched, out-of-band | proposed artifact diffs |

---

## 1 · Architect — the plan-first designer *(the moat lives here)*
- **Stage / fan-out:** 1 · Plan — runs once.
- **Reads:** [`editorial/dna.md`](../editorial/dna.md), the **Theme Brief** (`goal.md`), [`taxonomy.md`](../../docs/taxonomy.md), [`guardrails/connection.md`](../guardrails/connection.md) + [`constellation.md`](../guardrails/constellation.md), and the existing Content Graph **via the `ContentGraphRepository` read port** (to bridge to it and avoid duplicates).
- **Produces:** `plan.md` — every Piece concept (title + premise + Topic tags) and the full **Connection skeleton** (each origin→destination with its intended hook angle).
- **Tools:** `ContentGraphRepository` (read — dedup against existing Pieces).
- **Honors:** DNA, connection.md, constellation.md, the taxonomy.
- **Task:**
  1. Choose the constellation's Piece concepts spanning the Brief's target Topics.
  2. Design the Connection graph so the **Tier-1 invariants hold by construction** — especially I6 (≥1 cross-Topic per Piece), I4 (no dead ends), I7 (connected).
  3. Mark entry-worthy nodes (J3) that can open cold as a Daily Feature.
- **Done when:** `plan.md` present, no placeholders, all structural invariants satisfiable — **and the human approves the plan** (the Stage-1 gate; [ADR 0003](../../docs/adr/0003-plan-first-generation.md)).

## 2 · Researcher — the closed-book substrate builder
- **Stage / fan-out:** 2 · Source — per Piece.
- **Reads:** the Piece concept from `plan.md`, [`guardrails/sourcing.md`](../guardrails/sourcing.md), any Theme-Brief seed sources.
- **Produces:** `pieces/<id>/sources.md` (the **vetted claim pack**) + `pieces/<id>/grounding.json` (the ledger).
- **Tools:** `WebSourcePort` (Playwright fetch + **bounded citation-chasing**; **recall-first URL discovery, no search engine in V1** — [ADR 0011](../../docs/adr/0011-harness-tools-are-ports-web-sourcing-recall-first.md)).
- **Honors:** sourcing.md, [ADR 0005](../../docs/adr/0005-closed-book-grounding.md).
- **Task:** run the adversarial sub-pipeline — **2a Harvest** (candidate claims from internal recall; **recalled URLs fetched via the `WebSourcePort`, then citation-chased to the primary sources those hubs cite — no search engine, [ADR 0011](../../docs/adr/0011-harness-tools-are-ports-web-sourcing-recall-first.md)**) → **2b Vet** sources → **2c Corroborate** to the admission bar → **2d Refute** (red-team each surviving claim).
- **Done when:** claim pack present; every claim has a status + corroboration; ledger complete; a **thin source pack fails loud and early** (before the Writer runs), never papered over.

## 3 · Writer — closed-book narrative
- **Stage / fan-out:** 3 · Draft — per Piece.
- **Reads:** the Piece concept, the **vetted claim pack only** (closed-book), [`editorial/dna.md`](../editorial/dna.md), the active [Voice Profile](../editorial/voices/).
- **Produces:** `pieces/<id>/draft.md` — the Piece as ordered **Content Blocks**.
- **Honors:** DNA, the Voice Profile, the closed-book rule (no fact outside the pack).
- **Task:** write the Piece in the active voice using only pack facts; open concrete, build to the reframe, end on a doorway; emit structured blocks.
- **Done when:** `draft.md` present, blocks well-formed, **every factual assertion traceable to a claim** in the pack.

## 4 · Editor — the anti-slop pass + machine-QA loop
- **Stage / fan-out:** 4 · Edit — per Piece.
- **Reads:** `draft.md`, DNA, the Voice Profile, [`guardrails/piece.md`](../guardrails/piece.md).
- **Produces:** `pieces/<id>/piece.md` — the final Piece.
- **Honors:** piece.md, DNA, Voice Profile.
- **Task:** tone/pacing/anti-slop edit; then the **machine-QA judge** applies piece.md and **loops the edit** until pass or QA budget spent; then **4.5 grounding check** — every assertion maps to a verified claim, drift/embellishment cut or re-sourced.
- **Done when:** `piece.md` passes **all** piece.md checks *and* the grounding check; otherwise flagged/escalated, never silently shipped.

## 5 · Weaver — Connections & per-origin hooks
- **Stage / fan-out:** 5 · Wire — runs once.
- **Reads:** all finalized Pieces, the `plan.md` Connection skeleton, [`guardrails/connection.md`](../guardrails/connection.md).
- **Produces:** `connections.md` — every Connection with its **per-origin hook**.
- **Honors:** connection.md.
- **Task:** write each hook (a specific curiosity gap, anti-clickbait, per-origin, in voice); realize the planned skeleton; guarantee I4/I5/I6.
- **Done when:** every planned Connection realized with a **passing hook**; invariants I4–I6 hold; zero dead ends.

## 6 · Reviewer — Constellation QA
- **Stage / fan-out:** 6 · Constellation QA — runs once.
- **Reads:** the whole constellation, [`guardrails/constellation.md`](../guardrails/constellation.md).
- **Produces:** `qa.md` — Tier-1 invariant results + Tier-2 coherence verdict.
- **Honors:** constellation.md.
- **Task:** assert **Tier-1 invariants (I1–I8), binary**; judge **Tier-2 coherence (J1–J5)**; loop or flag.
- **Done when:** all Tier-1 invariants pass; Tier-2 flags resolved or escalated to the human queue. (Surviving Pieces then enter the human review gate — [ADR 0004](../../docs/adr/0004-human-ratified-learning-loop.md).)

## 7 · Distiller — the learning loop *(out-of-band, batched)*
- **Stage / fan-out:** not in the per-run pipeline; runs periodically over accumulated feedback.
- **Reads:** `feedback/verdicts.jsonl` + edit-diffs.
- **Produces:** a **proposed markdown diff** to DNA / guardrails / exemplars.
- **Honors:** [ADR 0004](../../docs/adr/0004-human-ratified-learning-loop.md) — the human **ratifies every diff**; nothing auto-merges.
- **Task:** batch-analyze verdicts → propose banned-phrase additions (from repeated deletions), new checks (from repeated reject reasons), exemplar promotions, DNA tweaks.
- **Done when:** a diff is proposed and **presented to the human**; only human-ratified diffs land.

---

## Publish — re-wire & re-QA the approved subset *(post-human-gate)*
Not an eighth agent: the **write step** that promotes human-approved Pieces into the Content Graph. Because the human approves Pieces one at a time and may reject some, the approved subset can violate the I4/I7 that QA verified over the *full* set. So publishing **re-runs the Weaver + Reviewer over the approved survivors** and writes only the re-validated set through the `ContentGraphRepository` **write** port ([ADR 0012](../../docs/adr/0012-publish-gate-rewire-and-reqa-approved-subset.md)). A survivor that can't be made contract-valid is flagged back to the human — never published into a broken state. The Weaver and Reviewer therefore run in **two modes**: the in-run pass over the planned constellation, and this post-approval pass over the approved subset.

After re-wire + re-QA, the human gives a **final wired-constellation approval** — the realized hooks (where taste lives) and the graph shape — before the write ([ADR 0013](../../docs/adr/0013-human-review-surface-is-the-file-workspace.md)). This is the third of the **three human gates** (plan → each Piece → wired constellation); all three run on the shared file workspace with a runtime-agnostic verdict contract, so review is identical under either runtime.
