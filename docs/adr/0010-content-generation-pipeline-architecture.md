# The content-generation pipeline: staged, plan-first, gated, dual-runtime

The generation subsystem is a **fixed, staged pipeline** — not a free-roaming agent. This ADR graduates the architecture developed in [content-harness.md](../content-harness.md) into a settled decision and ties together the ADRs it rests on ([0003](0003-plan-first-generation.md) plan-first, [0004](0004-human-ratified-learning-loop.md) learning loop, [0005](0005-closed-book-grounding.md) grounding, [0006](0006-generation-and-consumption-are-separate.md) generation/consumption separation).

## The pipeline

One run consumes an editorial **Theme Brief** + the global **Editorial DNA** and produces a **constellation** — a bounded, dead-end-free set of ~30 Pieces spanning 4–5 Topics, wired by cross-Topic Connections — written into the Content Graph.

| Stage | Owner | Deliverable | Fan-out |
| --- | --- | --- | --- |
| **0 · Gate** | — | Editorial DNA + Theme Brief present, no placeholders | — |
| **1 · Plan** | Architect | `plan.md` (Piece concepts + Connection skeleton) | once |
| **2 · Source** | Researcher | `pieces/<id>/sources.md` + `grounding.json` | per Piece |
| **3 · Draft** | Writer | `pieces/<id>/draft.md` | per Piece |
| **4 · Edit** | Editor | `pieces/<id>/piece.md` | per Piece |
| **5 · Wire** | Weaver | `connections.md` | once |
| **6 · Constellation QA** | Reviewer | `qa.md` | once |

Roster specs: [`harness/agents/README.md`](../../harness/agents/README.md).

## The load-bearing properties

1. **Plan-first.** The Architect designs the entire constellation graph before any Piece is written; downstream stages fill a graph whose shape is already fixed ([ADR 0003](0003-plan-first-generation.md)). This is what makes the structural guarantees holdable *by construction*.
2. **The deliverable-on-disk is the gate.** A stage cannot start until its prerequisite artifact exists (the we-os discipline). No implicit state.
3. **Fan-out in the middle.** Stages 2–4 map per Piece; 1, 5, 6 run once. Per-stage LLM-judge self-critique wraps 2–4 (per Piece) and 6 (constellation).
4. **Determinism by construction.** Fixed control flow (fixed stage order, gate short-circuit, bounded QA loop) **+** the Tier-1 outcome contract (invariants **I1–I8**, [`harness/guardrails/constellation.md`](../../harness/guardrails/constellation.md), including ≥1 cross-Topic Connection per Piece) = a deterministic *outcome*, not bit-identical prose.
5. **Closed-book grounding.** Stage 2 is an adversarial sub-pipeline (Harvest → Vet → Corroborate → Refute); the Writer drafts only from the vetted claim pack; a post-draft grounding check backstops it ([ADR 0005](0005-closed-book-grounding.md)).
6. **Three-layer quality, human is arbiter.** Encoded taste (guardrails) → machine-QA filter (loops the Editor) → the human ([ADR 0004](0004-human-ratified-learning-loop.md)). The human approves the Stage-1 plan and every Piece in V1; relaxation toward sampling is data-gated per Topic.
7. **Human-ratified learning.** A batched Distiller compiles human verdicts + edit-diffs into proposed markdown-artifact diffs; the human ratifies each ([ADR 0004](0004-human-ratified-learning-loop.md)).

## Dual runtime, one source of truth

The **markdown artifacts** ([`harness/`](../../harness/): DNA, Voice Profiles, guardrails, agent specs) **+ a shared stage manifest** (`stage → agent → deliverable → prerequisite → gate`, data not code) are the single source of truth. Two runtimes consume them:

- **Claude Code skills/agents** — interactive / dev + human-in-the-loop (authoring, iterating, the review gate).
- **LangGraph `StateGraph`** — deterministic / production; **authoritative for the outcome-contract guarantee** (the hand-built control flow lives here, not a free-roaming supervisor).

Parity is structural — both read the same specs + manifest; only the orchestration wiring is written twice, and a **parity test** on a fixture Brief asserts both emit contract-satisfying output.

## Why
- **Guarantees beat hope.** Anti-slop, grounding, and structural coherence are enforced *by construction* — the pipeline cannot produce otherwise — rather than trusting a self-lenient judge to catch exceptions. Same logic as plan-first and closed-book.
- **The moat becomes reviewable artifacts.** Topic selection, connection design, and taste live in human-readable files (the plan, the DNA, the guardrails), not opaque model behavior.
- **Ports the we-os discipline** the founder already trusts (markdown source of truth, Stage 0 gate, per-stage QA, ports-and-adapters).

## Trade-off
Far heavier than a single-prompt generator — six stages, a multi-round grounding sub-pipeline, two runtimes, and a human gate. Accepted: the product's entire value is being perceived as smart and trustworthy, and the first ~30 Pieces decide "smart" vs "AI junk." Failing loud and early (a thin source pack dies before drafting) is the point.

## Consequence
This ADR governs the **generation subsystem only**. Its sole output across the boundary is Pieces, Connections, and Topic tags written into the Content Graph ([ADR 0006](0006-generation-and-consumption-are-separate.md)); constellation, run id, theme brief, and grounding ledger never reach consumption. The living, tunable detail continues to evolve in [content-harness.md](../content-harness.md) and the [`harness/`](../../harness/) artifacts without reopening this ADR — only a change to the *shape* (stages, gates, determinism model, dual-runtime split) does.
