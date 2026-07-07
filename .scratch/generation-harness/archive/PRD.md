# PRD: The Content-Generation Harness

Status: completed
Feature: generation-harness
Depends on: `content-graph` (writes Pieces / Connections / Topics through the `ContentGraphRepository` write surface)

> This PRD implements the generation subsystem of [ADR 0010](../../docs/adr/0010-content-generation-pipeline-architecture.md) — the staged, plan-first, gated, dual-runtime pipeline. It **only writes** to the Content Graph; it knows nothing about users, Sessions, or the app ([ADR 0006](../../docs/adr/0006-generation-and-consumption-are-separate.md)).

## Problem Statement

The product's entire value is being perceived as **smart and trustworthy**, and the first ~30 Pieces decide "smart" vs "AI junk" — the moat is editorial taste and the #1 failure mode is **AI slop**. Two naive paths both fail:

- **By hand** doesn't scale past a demo, and can't guarantee the dense cross-Topic interconnection that makes the reader feel _"everything connects."_
- **A single-prompt generator** produces exactly the slop the product must avoid — flat summaries, fake insight, hedging, and confidently-wrong facts — because an LLM judge is self-lenient and passes the kind of prose an LLM writes.

The team needs a generation mechanism that produces grounded, on-voice, densely-interconnected Pieces **by construction** — where anti-slop, factual grounding, and structural coherence are _enforced by the pipeline's shape_, not hoped for — with the human as the final arbiter of quality, and the whole thing steerable through human-readable markdown rather than opaque model behavior.

## Solution

Implement the pipeline of [ADR 0010](../../docs/adr/0010-content-generation-pipeline-architecture.md) as a **deterministic LangGraph `StateGraph`** driven by the markdown specs already in [`harness/`](../../harness/) plus a **shared stage manifest** (`stage → agent → deliverable → prerequisite → gate`, data not code). One run consumes an editorial **Theme Brief** + the global **Editorial DNA** and produces a **constellation** — ~30 Pieces spanning 4–5 Topics, wired by cross-Topic Connections, written into the Content Graph.

| Stage                | Owner      | Deliverable                                      | Fan-out   |
| -------------------- | ---------- | ------------------------------------------------ | --------- |
| 0 · Gate             | —          | DNA + Theme Brief present, no placeholders       | —         |
| 1 · Plan             | Architect  | `plan.md` (Piece concepts + Connection skeleton) | once      |
| 2 · Source           | Researcher | `pieces/<id>/sources.md` + `grounding.json`      | per Piece |
| 3 · Draft            | Writer     | `pieces/<id>/draft.md`                           | per Piece |
| 4 · Edit             | Editor     | `pieces/<id>/piece.md`                           | per Piece |
| 5 · Wire             | Weaver     | `connections.md`                                 | once      |
| 6 · Constellation QA | Reviewer   | `qa.md`                                          | once      |

Load-bearing properties, all from [ADR 0010](../../docs/adr/0010-content-generation-pipeline-architecture.md): **the deliverable-on-disk is the gate** (no stage starts without its prerequisite artifact); **plan-first** (the whole graph is designed before any Piece is written, so structural guarantees hold by construction); **closed-book grounding** (Stage 2 is an adversarial sub-pipeline; the Writer drafts only from the vetted claim pack — [ADR 0005](../../docs/adr/0005-closed-book-grounding.md)); **three-layer quality** with the human as arbiter (encoded taste → machine-QA filter → human — [ADR 0004](../../docs/adr/0004-human-ratified-learning-loop.md)); and a **Tier-1 outcome contract (I1–I8)** that the run must satisfy or fail. Voice is pluggable via a Voice Profile text file, no code change.

## User Stories

_Actors: the **editor/curator** (the human operating and improving the harness), the **developer** building the pipeline, the **operator** running a batch, and the **pipeline itself** (its agents as system capabilities)._

**Planning (the moat)**

1. As the editor, I want to hand the harness a Theme Brief and have the Architect design the entire constellation — every Piece concept and the full Connection skeleton — before any prose is written, so that the graph's shape and its guarantees are fixed up front ([ADR 0003](../../docs/adr/0003-plan-first-generation.md)).
2. As the editor, I want to **approve the plan** before drafting begins, so that the most expensive stages only run on a constellation I've endorsed.
3. As the editor, I want the Architect to design so that every Piece will carry ≥1 cross-Topic Connection (I6) and no Piece is a dead end (I4), so that "everything connects" is structural, not decorative.
4. As the editor, I want the plan to mark entry-worthy nodes (J3), so that some Pieces can open cold as a Daily Feature.
5. As the pipeline, I want to refuse to start Stage 1 unless the Editorial DNA and a placeholder-free Theme Brief exist (Stage 0 Gate), so that no run proceeds on missing inputs.

**Grounding (closed-book truth)** 6. As the editor, I want each Piece researched closed-book — the Writer may use _only_ facts in a vetted claim pack — so that no confidently-wrong sentence from model memory ever ships ([ADR 0005](../../docs/adr/0005-closed-book-grounding.md)). 7. As the pipeline, I want Stage 2 to run Harvest → Vet → Corroborate → Refute, so that each surviving claim has cleared the corroboration bar and an adversarial red-team. 8. As the pipeline, I want internal-only uncorroborated claims **dropped by default** (flagged to the human only if load-bearing), so that echo-chamber myths and unsourced assertions don't enter the pack. 9. As the pipeline, I want a **thin source pack to fail loud and early — before the Writer runs** — so that a weak Piece dies at research rather than being papered over in prose. 10. As the editor, I want a per-Piece **grounding ledger** persisted (claim → tier → status → sources → refutation verdict), so that any shipped fact is inspectable and a wrong one is traceable to its exact source and round. 11. As the pipeline, I want a post-draft grounding check (Stage 4.5) mapping every factual assertion back to a verified claim, so that narrative drift or embellishment is cut or re-sourced.

**Drafting & anti-slop editing** 12. As the pipeline, I want the Writer to emit the Piece as **ordered Content Blocks** in the active Voice Profile, using only pack facts, so that the output matches the reader's schema and house voice. 13. As the editor, I want the Editor stage to run the machine-QA judge against [`guardrails/piece.md`](../../harness/guardrails/piece.md) and **loop until pass or the QA budget is spent**, so that obvious slop never reaches my review queue. 14. As the editor, I want the anti-slop checks to be **binary, concrete FAIL-if rules** (not "rate 1–10"), so that self-lenient scoring can't wave slop through. 15. As the editor, I want to swap the house voice by editing a Voice Profile markdown file with **no code change**, so that I can write in my voice, a guest's, or a brand's.

**Wiring & constellation QA** 16. As the pipeline, I want the Weaver to write every planned Connection with a **per-origin hook** (a specific curiosity gap, anti-clickbait, in voice), so that the traversable graph is realized with zero dead ends. 17. As the pipeline, I want Constellation QA to assert **Tier-1 invariants I1–I8 as binary pass/fail** and judge **Tier-2 coherence J1–J5**, so that a run either satisfies the outcome contract or fails — no soft warnings on the hard invariants. 18. As the operator, I want a run over the same Theme Brief to always satisfy the **same invariants** (deterministic _outcome_, not identical prose), so that the guarantee is a property of the pipeline, not of luck.

**Human gate & learning loop** 19. As the editor, I want to be the arbiter — approve / edit-then-approve / reject-with-reason **every Piece in V1** — so that the first impressions are mine, not a lenient judge's ([ADR 0004](../../docs/adr/0004-human-ratified-learning-loop.md)). 20. As the editor, I want every verdict and **edit-diff** captured to an append-only log, so that "the machine wrote X, I changed it to Y" becomes reusable taste signal. 21. As the editor, I want a batched Distiller to periodically read that log and **propose** markdown diffs to the DNA / guardrails / exemplars (new banned phrases from repeated deletions, new checks from repeated rejects), which **I ratify** — so that the system learns without any artifact mutating unsupervised. 22. As the editor, I want gate relaxation toward sampling to be **data-gated per Topic** by measured machine-vs-human agreement, so that the human load drops only where it's earned.

**Boundary & runtime** 23. As the pipeline, I want to write **only** Pieces, Connections, and Topic tags into the Content Graph — never constellation, run id, theme brief, or grounding ledger — so that the boundary to consumption stays clean ([ADR 0006](../../docs/adr/0006-generation-and-consumption-are-separate.md)). 24. As a developer, I want the LangGraph runtime and the Claude Code subagents to read the **same markdown specs + one stage manifest**, so that the two runtimes stay in parity and only the orchestration wiring is written twice. 25. As a developer, I want LLM and web-source access behind ports, so that the pipeline can be exercised end-to-end with deterministic fakes. 26. As the operator, I want each run's deliverables laid out under `harness/runs/<id>/`, so that the run is inspectable and a stage's gate is literally "does the prior file exist."

**Tools & publish integrity** 27. As the editor, I want the Researcher to source by fetching URLs the model recalls **and following those hub pages' cited links to the primary sources** (via Playwright, **no search engine**), so that V1 sourcing reaches primaries it couldn't name, isn't blocked by captchas, and a SERP service can drop in later behind the same port without changing the pipeline ([ADR 0011](../../docs/adr/0011-harness-tools-are-ports-web-sourcing-recall-first.md)). 28. As the product, I want a Piece the editor **rejected** to never leave a dead-end in the published graph, so that a real reader never hits a thread that goes nowhere — the publish step re-wires + re-QAs the approved subset before writing ([ADR 0012](../../docs/adr/0012-publish-gate-rewire-and-reqa-approved-subset.md)). 29. As the editor, I want the write step to publish only a re-validated survivor set (or flag a Piece it can't re-validate back to me), so that nothing ships into a broken graph state. 30. As the Architect, I want to read the existing Content Graph before planning, so that a new constellation bridges to prior Pieces and doesn't duplicate them. 31. As the editor, I want a **final approval of the wired constellation** — the realized hooks and the graph shape — before anything publishes, so that the taste-critical hook copy gets my eyes, not just machine QA ([ADR 0013](../../docs/adr/0013-human-review-surface-is-the-file-workspace.md)). 32. As the editor, I want the **same review workflow and captured signal whether the run was orchestrated by LangGraph or Claude Code**, so that my verdicts and edit-diffs mean the same thing regardless of runtime ([ADR 0013](../../docs/adr/0013-human-review-surface-is-the-file-workspace.md)).

## Implementation Decisions

**Modules built**

- A **pipeline orchestrator** as a LangGraph `StateGraph` with fixed stage order, the Stage-0 gate short-circuit, and a bounded QA loop (the hand-built control flow — _not_ a free-roaming supervisor).
- A **shared stage manifest** (data): `stage → agent → deliverable → prerequisite → gate`. Consumed by both the LangGraph runtime and the Claude Code subagents — the single source of truth alongside the [`harness/`](../../harness/) markdown.
- **Stage nodes / agents**, each driven by its spec card in [`harness/agents/README.md`](../../harness/agents/README.md): Architect, Researcher (with the 2a–2d sub-pipeline), Writer, Editor (with the machine-QA loop + 4.5 grounding check), Weaver, Reviewer. The out-of-band **Distiller** is a separate batched entry point, not a per-run stage.
- **Ports:** `LLMPort`; **`WebSourcePort`** — a Playwright adapter that fetches page content (renders JS) and **follows a page's cited links (bounded citation-chasing)**, **not** a Google-search scraper, with **recall-first URL discovery** in V1 and a **SERP adapter swappable in later** ([ADR 0011](../../docs/adr/0011-harness-tools-are-ports-web-sourcing-recall-first.md)); and the **`ContentGraphRepository`** used for both **read** (Architect dedup at plan time) and **write** (post-approval publish). The moat-bearing **guardrail evaluators** (piece / connection / constellation) are implemented as **pure functions** `artifact → [violations]`.
- A **run workspace** writer producing `harness/runs/<id>/`: `plan.md`, `pieces/<id>/{sources.md, grounding.json, draft.md, piece.md}`, `connections.md`, `qa.md`.
- The **human review surface** — the run's file workspace + a runtime-agnostic verdict contract (`feedback/verdicts.jsonl`), with **Claude Code as the V1 front-end** ([ADR 0013](../../docs/adr/0013-human-review-surface-is-the-file-workspace.md)). **Three gates** (plan → each Piece → wired constellation); **diff by preservation** (the machine draft is kept as `*.machine.md`, the human edits the copy, approval records the machine→human unified diff); each verdict line carries `runtime` + `model` + verdict + reason + diff + Topics.
- A **publish step** — post-human-gate, it re-wires + re-QAs the approved subset (Weaver + Reviewer in their second mode); after which the human gives a **final wired-constellation approval** (realized hooks + graph — [ADR 0013](../../docs/adr/0013-human-review-surface-is-the-file-workspace.md)) before it writes only the validated survivor set through the `ContentGraphRepository` write surface ([ADR 0012](../../docs/adr/0012-publish-gate-rewire-and-reqa-approved-subset.md)).

**Key decisions**

- **Theme Brief = a _medium_ brief** ([ADR 0003](../../docs/adr/0003-plan-first-generation.md) / [ADR 0004](../../docs/adr/0004-human-ratified-learning-loop.md)): the human provides through-line + target Topics + Piece-count (required) and optional seed sources / must-includes / entry-hints / must-avoids; the **Architect designs the rest** and the human approves at the plan gate. Template + worked example: [`harness/briefs/TEMPLATE.md`](../../harness/briefs/TEMPLATE.md). Stage 0 rejects a Brief with unfilled placeholders.
- **Gate = deliverable-on-disk.** A stage's start precondition is the existence of its prerequisite artifact; there is no implicit in-memory state a resumed run could disagree with.
- **Fan-out** stages 2–4 map per planned Piece; stages 1, 5, 6 run once. Per-stage LLM-judge self-critique wraps 2–4 (per Piece) and 6 (constellation).
- **Closed-book** ([ADR 0005](../../docs/adr/0005-closed-book-grounding.md)): the Writer's input is the vetted claim pack **only**; internal knowledge is a proposer/recall aid during research, never an authority. Corroboration bar per [`guardrails/sourcing.md`](../../harness/guardrails/sourcing.md): a primary source suffices alone; secondary/tertiary needs ≥2 independent sources; internal-only uncorroborated is dropped by default.
- **Three-layer quality, human is arbiter** ([ADR 0004](../../docs/adr/0004-human-ratified-learning-loop.md)): encoded taste (guardrails) → machine-QA filter (loops the Editor) → the human. Machine QA is a **bouncer, not the editor-in-chief**.
- **Determinism of outcome** = fixed control flow **+** Tier-1 contract (I1–I8, [`guardrails/constellation.md`](../../harness/guardrails/constellation.md)). Byte-reproducibility (pinning temperature/seed/model) is a **separate optional lever, deferred**.
- **Dual runtime, one source of truth** ([ADR 0010](../../docs/adr/0010-content-generation-pipeline-architecture.md)): V1 implements the **LangGraph runtime as authoritative** for the guarantee; the Claude Code subagent wiring reads the same specs + manifest. A parity test asserts both emit contract-satisfying output on a fixture Brief.
- **Human review surface & parity** ([ADR 0013](../../docs/adr/0013-human-review-surface-is-the-file-workspace.md)): the review surface is the **file workspace + a runtime-agnostic verdict contract**, not a runtime feature — both runtimes pause at the same **three gates** (plan → Piece → wired constellation), preserve the machine draft identically, and append the same `verdicts.jsonl`. Parity now covers the human gates; the parity test asserts it. Claude Code is the V1 front-end; a rendered preview is a fast-follow.
- **Boundary:** writes reach the Content Graph only as Pieces / Connections / Topics; generation-only concepts never cross ([ADR 0006](../../docs/adr/0006-generation-and-consumption-are-separate.md)).
- **Web sourcing is recall-first, then citation-chasing** ([ADR 0011](../../docs/adr/0011-harness-tools-are-ports-web-sourcing-recall-first.md)): the Researcher's recall proposes candidate URLs (the [ADR 0005](../../docs/adr/0005-closed-book-grounding.md) recall-aid role) — mostly **hub** pages — then **follows their cited links (bounded)** to reach the **primary sources** those hubs cite; Corroborate/Refute vet everything; **no search engine in V1**. The corroboration bar is unchanged — a claim that still can't reach ≥2 independent sources is **cut, not shipped**; a primary source suffices alone. A **SERP adapter** later widens yield without touching the bar. Fetched content feeds the grounding ledger and is snapshotted per run.
- **Publish gate — re-wire & re-QA survivors** ([ADR 0012](../../docs/adr/0012-publish-gate-rewire-and-reqa-approved-subset.md)): the human gate approves Pieces one-by-one and may reject some, so the write step is **not** a bare insert — after verdicts, **Weaver + Reviewer re-run over the approved subset** and only the re-validated survivor set is written, so the _published_ graph is I1–I8-valid **as shipped** (no dead-ends in front of a reader). A survivor that can't be re-validated is flagged back to the human. Weaver and Reviewer thus run in two modes: in-run over the planned constellation, and post-approval over the survivors.
- **Text-only V1:** no visual-sourcing stage; the Writer emits text Content Blocks only ([ADR 0007](../../docs/adr/0007-visual-provenance-sourced-or-data-grounded.md)).

## Testing Decisions

**What a good test is here:** it asserts the pipeline's _external guarantees_ on controlled inputs (does the run satisfy the outcome contract? does a given artifact pass or fail a guardrail?) — not the wording of any LLM output, which is stochastic. LLM and search are faked so tests are deterministic and offline.

- **Primary integration seam — the outcome contract.** Run the `StateGraph` end-to-end over a **fixture Theme Brief** with fake `LLMPort` + fake `WebSourcePort` + the in-memory `ContentGraphRepository` from `content-graph`; assert **Tier-1 invariants I1–I8** on what was written (count, required fields, Topic coverage, zero dead ends, resolvable Connections, ≥1 cross-Topic per Piece, connectedness, complete grounding ledger).
- **Highest-value unit seam — guardrail evaluators as pure functions.** Feed crafted fixtures and assert the specific violation:
  - a Piece opening on a definition → FAIL A1; a paragraph of pure abstraction → FAIL B1; a banned-filler phrase → FAIL D3.
  - a shared-Topic-adjacency Connection → FAIL A1; a hook identical from any origin → FAIL B3.
  - a constellation with a dead-end → FAIL I4; a Connection to a missing Piece → FAIL I5; a Piece with no cross-Topic outbound → FAIL I6.
- **Grounding behavior.** An internal-only uncorroborated claim is dropped/flagged, never silently kept; a thin source pack **fails before** the Writer stage runs.
- **Web sourcing (faked).** The Researcher fetches only through a faked `WebSourcePort` (canned page content keyed by URL); assert a claim whose second independent source can't be reached from recalled URLs is **cut, not shipped**, while a single-primary claim survives.
- **Publish gate.** Reject a Piece from the fixture constellation → the publish step re-wires + re-QAs the survivors → assert the **written** graph still satisfies I4/I5/I6/I7 (no dead-ends, still connected), and a survivor that can't be re-validated is **flagged, not written**.
- **Gate discipline.** A stage refuses to start when its prerequisite deliverable is absent.
- **Parity.** On the fixture Brief, both runtimes emit contract-satisfying output (structure V1 for this even if the Claude Code wiring lands as a fast-follow).
- **Review parity & capture.** Assert both runtimes pause at the same three gates and — given the same verdict + edit — append an identical `verdicts.jsonl` line (runtime/model aside) and compute the same machine→human diff from the preserved `*.machine.md`.
- **Prior art:** the in-memory `ContentGraphRepository` fake and contract-test pattern from `content-graph`.

## Out of Scope

- **Visual sourcing / generation** — text-only V1; no visual stage ([ADR 0007](../../docs/adr/0007-visual-provenance-sourced-or-data-grounded.md)).
- **SERP / search-engine discovery** — V1 is recall-first Playwright fetch; a SERP adapter is deferred behind the same `WebSourcePort`, and deep interactive navigation (logins, form-driven search) is out of V1 scope ([ADR 0011](../../docs/adr/0011-harness-tools-are-ports-web-sourcing-recall-first.md)).
- **Fine-tuning** — the accumulated verdict corpus may unlock it much later; not V1 ([ADR 0004](../../docs/adr/0004-human-ratified-learning-loop.md)).
- **Automatic gate relaxation** beyond capturing the calibration signal — relaxation is data-gated and manual for now.
- **A rendered / web review app** — V1 review is the file workspace via Claude Code ([ADR 0013](../../docs/adr/0013-human-review-surface-is-the-file-workspace.md)); a rendered reader-fidelity preview is a fast-follow that reuses the consumption renderer.
- **Byte-for-byte reproducibility** (temperature/seed/model pinning) — a separate optional lever.
- **Anything consumption** — Sessions, Tapestry, the reader API, personalization.

## Further Notes

- The moat lives in two places this PRD must treat as first-class: the **Architect's plan** (topic selection + how Pieces connect) and the **guardrail evaluators** (encoded taste). Both are human-readable artifacts by design.
- The living, tunable detail continues to evolve in [content-harness.md](../../docs/content-harness.md) and the [`harness/`](../../harness/) artifacts without reopening [ADR 0010](../../docs/adr/0010-content-generation-pipeline-architecture.md); only a change to the pipeline's _shape_ would.
- The harness's **tool surface** ([ADR 0011](../../docs/adr/0011-harness-tools-are-ports-web-sourcing-recall-first.md)) and **publish gate** ([ADR 0012](../../docs/adr/0012-publish-gate-rewire-and-reqa-approved-subset.md)) are the two decisions that make it an _agentic loop with tools_ rather than a pure file transform — see those ADRs.
- Depends on `content-graph` for both the **read** surface (Architect dedup) and the **write** surface (publish); it shares no code with `consumption-app`.

## Completion

- Completed: 2026-07-07
- Commit: `7af81e040b8b2425c330f3f874ccc206be43fe85`
