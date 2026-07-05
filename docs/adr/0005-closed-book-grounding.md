# Closed-book grounding: the model proposes, external sources decide

Pieces are written **closed-book**: the Writer may use only facts present in a vetted **claim pack** produced upstream. It may **not** introduce facts from its own parametric knowledge at drafting time. The model's internal knowledge is used *earlier* — as a **proposer and recall aid** during research, and to decide where to look for sources — but **no internally-recalled claim enters the pack until it is corroborated against credible external sources.** Internal knowledge is a hypothesis generator, never an authority.

Grounding is deliberately **non-trivial** — multiple adversarial rounds (Stage 2 is a sub-pipeline, backstopped post-draft):

1. **Harvest** candidate claims (internal recall + external search).
2. **Vet** each source against a credibility rubric (`guardrails/sourcing.md`); human-provided sources enter at a trusted tier but are still checked.
3. **Corroborate** each claim against external sources; uncorroborated internal-only claims are dropped or flagged to the human — never silently kept.
4. **Refute** (adversarial) — a red-team verifier actively tries to break each surviving claim.
5. **Post-draft grounding check** — every factual assertion in the draft must map back to a verified claim; narrative drift or embellishment is cut or re-sourced.

"Is it true" (checkable against the pack) and "is it slop" (taste) are **separate** QA judgments, never merged into one score. The **full grounding record** — every corroborated source (citation, tier, supporting excerpt, credibility assessment, retrieval time), its claim mapping, and each round's verdict — is stored per Piece whether or not shown to users, so any fact is inspectable and the chain is debuggable if a wrong fact ever ships.

**Corroboration standard (the admission bar):** a **primary/authoritative** source is sufficient alone; a **secondary/tertiary** claim needs **≥2 *independent* credible sources** (wire/echo repeats collapse to one — this kills "everyone repeats the same myth"); **internal-only uncorroborated** claims are dropped by default, flagged to the human only if load-bearing; **human-provided** sources count as a primary but still pass a basic reliability check. The standard deliberately *protects* surprising single-primary-source facts while cutting unsourced and echo-chamber claims.

**Why:**
- The product's entire value is being perceived as *smart and trustworthy*; one confidently-wrong Piece in the first ~30 destroys that. **Provenance-by-construction beats verify-after** — the same logic as plan-first: the guarantee holds because the pipeline *cannot* produce otherwise, not because a lenient LLM judge hopefully caught the exceptions.
- Ports the we-os research discipline (evidence-based, cite the source, flag gaps honestly, never invent what the source omits).
- Locates the Writer's creativity in **narrative, framing, and compression** over a fixed true substrate — exactly the "story, not encyclopedia" voice the product needs.

**Trade-off:** the grounding stage is heavy, and the Writer cannot paper over gaps — a thin source pack yields a thin Piece that fails Stage-2 QA *loudly and early, before drafting*. Accepted; failing loud before the Writer runs is the point.
