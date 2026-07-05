# Content-Generation Harness — Design Notes

Living design record for the agentic loop that produces Pieces, Connections, and hooks. Modeled on the [we-os agent-harness](../../we-os/agent-harness/README.md) pattern: **markdown as the single source of truth**, two runtimes over the same markdown (interactive Claude Code skills/agents **and** a deterministic LangGraph `StateGraph`), a Stage 0 gate, and a per-stage LLM-as-judge self-critique loop.

This doc accumulates decisions as we design. Settled, hard-to-reverse choices graduate to ADRs.

## Decisions so far

### Run-unit = a themed cross-Topic constellation
One run takes an editorial **theme brief** and generates a bounded, internally-dense, **dead-end-free** set of ~30 Pieces that span 4–5 Topics, wired together with cross-Topic Connections. The constellation is an **ephemeral generation input** (a theme), not a stored domain entity — the durable output is Pieces + Connections. (Supersedes an earlier "run = a Spool" framing; a Spool/Topic is a classification tag, not a batch — see [ADR 0002](adr/0002-taxonomy-and-content-graph-are-separate.md).) The run-unit is the direct analogue of a we-os *campaign*.

### Pipeline = plan-first, fan-out in the middle
Generation is **plan-first**: an Architect designs the full constellation graph (all Piece concepts + the Connection skeleton) before any Piece is written; downstream stages fill in a graph whose shape is already fixed. See [ADR 0003](adr/0003-plan-first-generation.md). This is what makes the determinism outcome-contract guaranteed *by construction*, and it puts the moat (topic selection + how they connect) into one human-reviewable artifact.

Stages, in the we-os idiom (the prerequisite deliverable existing on disk *is* the gate):

| Stage | Owner | Deliverable |
| --- | --- | --- |
| **0 · Gate** | — | Editorial DNA + Theme Brief present, no placeholders |
| **1 · Plan** | Architect | `plan.md` — Piece concepts (title + premise + Topic tags) + Connection skeleton |
| **2 · Source** | Researcher ×N | `pieces/<id>/sources.md` — vetted sources + cited facts |
| **3 · Draft** | Writer ×N | `pieces/<id>/draft.md` |
| **4 · Edit** | Editor ×N | `pieces/<id>/piece.md` — the anti-slop tone/pacing pass |
| **5 · Wire** | Weaver | `connections.md` — Connections + per-origin hooks, zero dead ends |
| **6 · Constellation QA** | Reviewer | `qa.md` — outcome-contract invariants + journey coherence |

Stages 2–4 **fan out** (map over the planned Pieces); 1, 5, 6 run once. Per-stage LLM-judge self-critique wraps 2–4 (per Piece) and 6 (constellation). **Editorial DNA** is global (your taste, reused every run); the **Theme Brief** is the run's `goal.md`.

### Editorial quality has three layers; the human is the arbiter
An LLM judge is **self-lenient** — it passes the kind of prose an LLM writes — so a QA reviewer alone cannot guarantee quality. The hard rule (from the idea doc) is that **AI must not decide editorial quality**. Quality is therefore enforced in three layers:

1. **Encoded taste (guardrails).** The anti-slop rubric is *concrete failure-mode checks*, never "rate 1–10" — e.g. "opens with a concrete scene or fact, not a definition", "every paragraph has a specific checkable detail", "zero banned-filler phrases", "contains a surprising reframe", "passes the dinner-party test" — plus labeled exemplars ("match the great one").
2. **Machine QA (a filter, not the judge).** Strips *obvious* slop and loops the Editor, so junk never reaches the human. A bouncer, not the editor-in-chief.
3. **The human (the arbiter).** Ground truth for quality.

**Gate policy — tiered, and relaxation is earned (option c).** The human approves the Stage-1 Plan and **every Piece for V1** (the first ~30 form first impressions — no slop leak affordable). Relaxation toward sampling is **data-gated per Topic** by measured machine-QA-vs-human agreement. The human is always an *editor, never a writer*.

### Fact-grounding: closed-book, multi-round
Quality also means *true*. Pieces are written **closed-book** — the Writer uses only facts in an upstream **vetted claim pack** and may not add facts from its own memory at draft time. Internal knowledge is a *proposer / recall aid* (and picks where to search), **never an authority**: no internally-recalled claim enters the pack until corroborated by credible external sources. See [ADR 0005](adr/0005-closed-book-grounding.md).

Grounding is deliberately **non-trivial** — Stage 2 is itself a multi-round adversarial sub-pipeline, backstopped post-draft:

| Round | Role | Job |
| --- | --- | --- |
| **2a · Harvest** | Researcher | candidate atomic claims from internal recall + external search |
| **2b · Vet sources** | Vetter | score each source vs `guardrails/sourcing.md` (primary/secondary, authority, recency, bias, corroboration, retractions); human-provided sources trusted-but-checked |
| **2c · Corroborate** | Verifier | each claim clears the corroboration bar; internal-only uncorroborated claims dropped or flagged — never silently kept |
| **2d · Refute** (adversarial) | Red-team | actively try to break each surviving claim (contradictions, misconceptions, bad dates/numbers) |
| **→ vetted claim pack** | | the closed-book substrate |
| **4.5 · Grounding check** | Fact-check verifier | every factual assertion in the draft maps to a verified claim; drift/embellishment cut or re-sourced |

"Is it true" (vs the pack) and "is it slop" (taste) are **separate** reviewers, never one blurry score. The model chooses external sources autonomously but **guided by `guardrails/sourcing.md`**; the Theme Brief may inject human-curated seed sources at a trusted tier.

**Corroboration standard (the admission bar for Round 2c):**
- A **primary/authoritative** source (the study, official record, dataset, primary document, the person) is **sufficient alone**.
- A **secondary/tertiary** claim needs **≥2 independent credible sources** — *independent* = not citing each other, not the same origin; wire/echo repeats collapse to one. (Kills "everyone repeats the same myth".)
- **Internal-only, uncorroborated** claims are **dropped by default**; **flagged to the human** only if load-bearing for the premise (source it or cut).
- **Human-provided** sources count as a primary (trusted tier) but still pass a basic reliability check.

The bar deliberately *protects* surprising single-primary-source facts while cutting unsourced and echo-chamber claims. This spec seeds `guardrails/sourcing.md`.

**Grounding ledger (audit + debug).** Each run stores a per-Piece grounding record (e.g. `pieces/<id>/grounding.json`): per **claim** — text, tier, status (verified / dropped / flagged), corroborating sources, refutation verdict; per **source** — citation, tier, credibility assessment (why it passed 2b), supporting excerpt, retrieval timestamp. Persisted regardless of display, so any fact is inspectable and a shipped error is traceable to the exact source and round — which then becomes a distillation signal into `guardrails/sourcing.md`.

### Tools & seams — tool-using loops inside a fixed DAG

[ADR 0010](adr/0010-content-generation-pipeline-architecture.md) fixes the *orchestration* as a deterministic staged DAG, not a free-roaming agent. *Within* a stage, an agent is a **tool-using LLM running a bounded loop** (the Researcher's Harvest→Vet→Corroborate→Refute; the Editor's QA loop). Those loops reach outside the run workspace through exactly **two ports** — everything else is file-in / file-out ([ADR 0011](adr/0011-harness-tools-are-ports-web-sourcing-recall-first.md)):

| Port | Adapter (V1) | Used by | For |
| --- | --- | --- | --- |
| `WebSourcePort` | Playwright (fetch/navigate; **no** Google-search scraping) | Researcher | fetching source content |
| `ContentGraphRepository` | Postgres | Architect (read) + publish step (write) | dedup at plan time; publishing approved content |

**Web sourcing is recall-first in V1:** the model's parametric recall proposes *candidate URLs* (the [ADR 0005](adr/0005-closed-book-grounding.md) recall-aid role), Playwright fetches them **and follows their cited links (bounded) to reach the primary sources hub pages cite** — *recall a hub → chase its citations → vet the primaries* — and the Corroborate/Refute rounds vet everything. No `search(query)` in the V1 port; a **SERP adapter** swaps in later to widen yield **without touching the corroboration bar** — a secondary-only claim that can't reach ≥2 independent sources from recalled URLs is cut, not shipped, while a primary source still suffices alone. Fetched content feeds the grounding ledger (excerpt + timestamp) and is snapshotted per run for audit and politeness. This refines "generation writes, consumption reads": generation **read+writes** Content-Graph content (the Architect reads to avoid duplicates); consumption only reads it — still [ADR 0006](adr/0006-generation-and-consumption-are-separate.md)-clean.

### The publish gate — re-wire & re-QA the approved subset

Constellation QA verifies I1–I8 over the **whole** constellation, but the human gate approves Pieces one at a time and may **reject** some — which can leave a survivor as a **dead end (I4)** or fragment the graph (I7). Since the Content Graph is the **published** store the reader traverses, publishing is **not** a bare insert: after the human's verdicts, **Weaver + Reviewer re-run over the approved subset**, and only the re-validated survivor set is written ([ADR 0012](adr/0012-publish-gate-rewire-and-reqa-approved-subset.md)). A survivor that can't be made contract-valid is flagged back to the human, never published into a broken state. The invariant holds on **what ships**, not merely on what QA first saw.

## The self-learning loop (human-in-the-loop, governed)

"Self-learning" means the system **compiles human taste into the markdown artifacts the agents read** — not the model retraining itself. The memory that improves is files in git, not model weights (see [ADR 0004](adr/0004-human-ratified-learning-loop.md)). Fine-tuning is a much-later option the accumulated verdict corpus unlocks; not V1.

### The memory (artifacts that "learn")

These live under the harness artifact root **`harness/`** (mirrors the we-os layout); paths below are relative to it.

| Artifact | Role | Who writes it |
| --- | --- | --- |
| `editorial/dna.md` | Global taste / quality bar — the constitution ✅ *authored* | Human seeds; distillation proposes tweaks |
| `editorial/voices/<name>.md` | **Voice Profile** — swappable house voice (register + do/don't + exemplars); default `narrative-nonfiction` ✅ | Human authors; swap with **no code change** |
| `guardrails/piece.md` · `guardrails/constellation.md` | Concrete anti-slop **checks** | Human + distillation |
| `editorial/exemplars/{great,slop}/` | Labeled Pieces + *why* — few-shot fuel + reference | Promoted from human verdicts |
| `feedback/verdicts.jsonl` | Append-only: Piece id, verdict, **edit-diff**, reason, Topics, ts | The review UI |
| calibration (computed) | Per-Topic machine-vs-human agreement → gate policy | Derived from verdicts |

### The loop

- **A · Generate (within-run self-critique).** Gate → Architect plans → human approves plan → fan-out Source/Draft/Edit; each per-Piece machine QA reads `guardrails/piece.md` **and retrieves exemplars as few-shot**, emits verdict + specific violations, loops the Editor until pass or QA budget spent → Wire → Constellation QA.
- **B · Human gate (the arbiter).** Three gates — **plan → each Piece → the wired constellation** (realized hooks + graph, after the [ADR 0012](adr/0012-publish-gate-rewire-and-reqa-approved-subset.md) re-wire pass) — each **approve / edit-then-approve / reject-with-reason**. Every action → `verdicts.jsonl`; an edit captures the machine→human **diff** (the richest signal: "machine wrote X, human changed it to Y"). The surface is the **file workspace + a runtime-agnostic verdict contract**, Claude Code being the V1 front-end ([ADR 0013](adr/0013-human-review-surface-is-the-file-workspace.md)).
- **C · Distill (governed, batched).** A distillation agent periodically reads accumulated verdicts + edit-diffs and **proposes** artifact updates (banned phrases from repeated deletions, new checks from repeated reject reasons, exemplar promotions, DNA tweaks) as a markdown diff. **The human ratifies each diff.** Nothing mutates unsupervised. Cadence: every N verdicts / periodic — not continuous.
- **D · Calibrate & relax.** Compute per-Topic agreement; where proven high over enough samples, relax that Topic's gate from approve-all → sample. Data-gated.

Next run reads the sharpened artifacts → drafts start closer to the bar → less human correction → the loop tightens. The flywheel: **taste → verdicts + edit-diffs → distilled into DNA/rubric/exemplars → better drafts + sharper QA → less correction → attention freed for new Topics.**

### The human review surface

The gate runs on the **run's file workspace**, not a bespoke app — the same substrate both runtimes share, so **review is runtime-agnostic** ([ADR 0013](adr/0013-human-review-surface-is-the-file-workspace.md)). Both the LangGraph and Claude Code runtimes write the same deliverables, pause at the same **three gates**, preserve the machine draft the same way, and append to the same `verdicts.jsonl`; **Claude Code is the V1 front-end** over it (a rendered reader-fidelity preview is a fast-follow that reuses the consumption renderer). **Diff by preservation:** the machine output is kept (`*.machine.md`), the human edits the working copy, and approval records the unified machine→human diff. The verdict line carries `runtime` + `model` alongside verdict / reason / diff / Topics — precisely because both runtimes share the workflow, so calibration can tell a runtime-invariant signal from a model artifact. Parity ([ADR 0010](adr/0010-content-generation-pipeline-architecture.md)) now covers the gates too, and the parity test asserts it.

### Failure modes this must guard against
- **Rubric reward-hacking** — only-ever-adding-checks teaches letter-not-spirit. Guard: keep holistic exemplars beside the checklist; periodically review *approved* Pieces too.
- **Silent leniency / rubber-stamping** — calibration must weight **edits and rejections**, not approve-rate; rising average edit-distance is a warning even amid "approvals".
- **Volume mismatch** — markdown/exemplar learning works at *tens* of examples; fine-tuning needs *thousands*. Start with the former.

## Constraints (flagged now, specifics deferred)

### Deterministic outcome — REQUIRED
Every run must produce a deterministic **outcome**, in this precise sense:
- **Deterministic control flow** — fixed stage order, gate short-circuit, bounded QA loop (the hand-built `StateGraph`, not a free-roaming supervisor).
- **A fixed outcome contract** — every run over the same brief satisfies the same invariants: target Piece count met; every Connection resolves to a Piece *inside* the constellation (zero dead ends); every hook and required field present; every stage passed its QA gate.

This is determinism of the output's **guarantees**, not bit-identical prose (LLM token output is stochastic). Whether we *additionally* pin temperature/seed/model for byte-reproducibility and auditability is a separate lever, TBD. The full invariant list is now specified as **Tier 1 (I1–I8)** of [`harness/guardrails/constellation.md`](../harness/guardrails/constellation.md) — including the structural **≥1 cross-Topic Connection per Piece** guarantee.

## Scope note — V1 is text-only

The harness produces **text Pieces only** for V1. The consumer schema reserves first-class `image`/`gif`/`diagram` blocks, but they are not populated until a future phase — and when they are, visuals are **sourced or data-grounded, never fabricated** (no AI-generated photorealistic imagery), extending the grounding ledger to pixels. See [ADR 0007](adr/0007-visual-provenance-sourced-or-data-grounded.md). No visual-sourcing stage exists in the V1 pipeline.

## Open / next

- ~~Sourcing & fact-grounding~~ — ✅ designed ([ADR 0005](adr/0005-closed-book-grounding.md) + the grounding sub-pipeline above)
- ~~Anti-slop rubric~~ — ✅ authored: [`piece.md`](../harness/guardrails/piece.md), [`connection.md`](../harness/guardrails/connection.md), [`constellation.md`](../harness/guardrails/constellation.md) (Tier-1 invariants I1–I8 = the outcome contract). First exemplars still to be promoted from human verdicts.
- ~~Editorial DNA~~ — ✅ authored: [`dna.md`](../harness/editorial/dna.md) + pluggable [Voice Profile](../harness/editorial/voices/narrative-nonfiction.md); voice swappable via text file, no code
- ~~Agent roster & per-agent specs~~ — ✅ authored: [`harness/agents/README.md`](../harness/agents/README.md) (7 spec cards) + [`sourcing.md`](../harness/guardrails/sourcing.md)
- ~~Dual runtime parity~~ — ✅ decided ([ADR 0010](adr/0010-content-generation-pipeline-architecture.md)): markdown + shared stage manifest as the single source of truth; Claude Code = interactive/dev/human-review, LangGraph = deterministic/production (authoritative for the guarantee)
- ~~Graduate the pipeline architecture to an ADR~~ — ✅ [ADR 0010](adr/0010-content-generation-pipeline-architecture.md)
- ~~Tool surface & web sourcing~~ — ✅ decided ([ADR 0011](adr/0011-harness-tools-are-ports-web-sourcing-recall-first.md)): two ports (`WebSourcePort`, `ContentGraphRepository`); recall-first Playwright fetch, no search engine, SERP-swappable later
- ~~Publish integrity under partial human approval~~ — ✅ decided ([ADR 0012](adr/0012-publish-gate-rewire-and-reqa-approved-subset.md)): re-wire + re-QA the approved subset; the published graph is I1–I8-valid as shipped
- ~~Theme Brief shape & template~~ — ✅ authored ([`harness/briefs/TEMPLATE.md`](../harness/briefs/TEMPLATE.md)): a **medium brief** — the human sets through-line + target Topics + Piece-count (+ optional seed sources / must-includes / entry-hints / must-avoids); the Architect designs the rest; you approve at the plan gate ([ADR 0003](adr/0003-plan-first-generation.md))
- ~~Human review surface~~ — ✅ decided ([ADR 0013](adr/0013-human-review-surface-is-the-file-workspace.md)): the run's file workspace + a runtime-agnostic verdict contract, Claude Code as V1 front-end; **three gates** (plan → Piece → wired constellation); diff-by-preservation; review parity across both runtimes

**Harness design is complete.** What remains is implementation (via `/to-prd` → `/to-issues` → build): the LangGraph `StateGraph`, the shared stage manifest, the Claude Code skill/subagent wiring, and promoting the first exemplars from human verdicts.
