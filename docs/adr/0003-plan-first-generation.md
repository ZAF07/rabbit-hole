# Content is generated plan-first, not organically

The content-generation harness designs the **entire constellation** — all Piece concepts and the full Connection skeleton — in a single up-front planning stage (the Architect), before any Piece is drafted. Downstream stages only fill in a graph whose shape is already fixed. The rejected alternative is **organic growth**: write a Piece, extract its natural Connections, queue those as new Pieces, and repeat until the target size is reached.

**Why:**
- **Determinism by construction.** The outcome contract (target Piece count, full connectivity, zero dead ends, bounded size) is guaranteed because the target graph exists *before* generation starts. Organic growth cannot promise a bounded, dead-end-free constellation, nor reliably know when to stop.
- **The moat becomes a reviewable artifact.** The product's moat is "choosing fascinating topics *and connecting them well*." Plan-first makes topic selection and the cross-Topic Connections an explicit Stage-1 plan a human approves — not an accidental byproduct of what a model happened to write.
- **Consistency with governance.** Mirrors the we-os rule "strategy before content; agents cannot bypass upstream decisions." The Architect's plan is the strategy; Pieces are the content.

**Trade-off:** Less emergent surprise from unplanned graph growth. We accept this because the surprise users actually value comes from the Architect's editorial *taste* (encoded in Editorial DNA), which is controllable — not from stochastic graph wander, which is not.
