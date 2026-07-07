# `decode.py` stays the single shape authority; the bounded revise-loops stay inlined

An architecture review (2026-07-07) split the 1279-line `stages.py` into a per-agent `stages/` package — one deep module per pipeline actor (Architect…Reviewer) behind the unchanged `run_stage_*(ctx)` interface, with cross-agent helpers in `stages/_kernel.py`. That refactor is settled and needs no ADR — it moved no logic and changed no seam ([ADR 0014](0014-harness-code-lives-in-src-harness.md) already fixes where harness code lives). This ADR records two *follow-up* candidates the same review considered and **declined**, so later reviews don't re-suggest them.

## Decisions

1. **`harness/pipeline/decode.py` remains the single authority on LLM response *shape* — it is not fragmented per agent.** The per-agent split already colocated each purpose's *request*-building with its agent module, which was the real locality win. The decoders that remain are overwhelmingly **shared primitives**: `decode_object` (4 agents), `decode_object_list` (3), `decode_piece_payload` (writer + editor). Only `decode_plan` is single-agent, and moving it out to chase that one case would trade away a coherent module for a marginal gain. `decode.py` passes the deletion test — delete it and `LLMResponseError` shape-validation smears across every agent — so it stays whole. Colocating a purpose's request and decode was **candidate B**; A absorbed the part of it worth having.

2. **The Weaver's and Editor's bounded revise-loops stay inlined — no shared `refine(propose, arbitrate, budget)` module.** The two loops are structurally heterogeneous: `weaver._realize_hook` re-proposes the *same* purpose with violation feedback, returns the candidate, and **raises** on budget exhaustion; `editor._grounding_check` is two-phase (check `editor.ground` → propose `editor.cut` → re-check), pairs *different* purposes, adds an `evaluate_piece` re-check, and **returns a typed `_EditResult`** rather than raising. A shared abstraction would have to absorb all of that — its interface would be as complex as the two loops it replaced, i.e. a **shallow** module. (The Editor's machine-QA loop is a third case, but it runs *inside* `run_agent` behind the port, not as a code-level loop at all.) Extracting this loop was **candidate C**, ranked Speculative; on inspection it is net-negative.

## Why

- **A deep module earns its interface.** `decode.py` hides real shape-validation behaviour behind a small surface and is reused across every agent; that is depth. A `refine` over two dissimilar loops would be breadth masquerading as reuse — the anti-pattern the design vocabulary calls shallow.
- **Avoid slop, including abstraction slop.** The moat is editorial taste, and taste includes *not* adding indirection that doesn't pay for itself. One adapter is a hypothetical seam; two heterogeneous loops are not one seam.

## Consequence

Governs harness internals only; no seam, no runtime behaviour, and nothing crossing the [ADR 0006](0006-generation-and-consumption-are-separate.md) boundary changes. If a *third* bounded revise-loop appears that genuinely shares the shape of an existing one — same propose/check purpose pairing, same return convention — Decision 2 is worth reopening then, with two real call sites to design against. Until that exists, the loops stay where they read most locally: inside their agent.
