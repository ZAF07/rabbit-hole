# Anti-Slop Guardrails — Connection & hook checks

The quality bar for a **Connection** (the directed link between two Pieces) and its **hook** (the per-origin lure). Connections are the product's crown jewels — the surprising, often cross-Topic jumps that make the reader feel *"everything connects"* ([ADR 0002](../../docs/adr/0002-taxonomy-and-content-graph-are-separate.md)). Applied by the Weaver (Stage 5) and Constellation QA (Stage 6). Same rules as [piece.md](piece.md): binary **FAIL-if** checks; truth is a separate judgment.

## A · The Connection itself
- **A1 · Earns the jump.** FAIL if the link is mere shared-Topic adjacency ("both about economics") rather than a real, specific relationship between *these two* Pieces.
- **A2 · True, not a stretch.** FAIL if the connecting relationship isn't grounded — it must be real, not a rhetorical bridge. *A surprising connection that isn't true is the worst failure there is: fake insight at the graph level.*
- **A3 · Prizes the non-obvious — honestly.** A cross-Topic Connection that reveals a hidden dependency (Engineering→Geopolitics) is worth more than an in-Topic next-step. But **surprise never overrides truth (A2)**: a strained "surprising" link is worse than an honest obvious one. Obvious in-Topic links are allowed as connective tissue; a constellation that is *all* obvious is failed at the constellation level, not here. Moreover, **every Piece must carry ≥1 cross-Topic outbound Connection** — a hard constellation invariant ([constellation.md](constellation.md) I6), designed in by the Architect at plan time.
- **A4 · Promise matches destination.** FAIL if the hook's promise doesn't match what the destination Piece actually delivers.

## B · The hook (per-origin lure)
- **B1 · A real curiosity gap.** FAIL if the hook doesn't open a *specific* question the destination answers. Not "Learn about GPS" — a gap: "Why does your phone's map depend on Einstein being right?"
- **B2 · Pays off — no clickbait.** FAIL if the hook overpromises relative to the Piece. A curiosity gap the Piece *closes* is the goal; a bait it can't honor is the cardinal sin (it's the retention-side twin of fake insight).
- **B3 · Specific to the pair.** FAIL if the hook would read identically from any origin. It must be written for *this* jump — the per-origin property ([CONTEXT.md](../../CONTEXT.md)).
- **B4 · Voice-conformant.** FAIL if it violates the active Voice Profile — a hook is micro-copy in the house voice.
- **B5 · No banned-filler.** Inherits piece.md check D3.

## What this does NOT judge
- Constellation-level shape (dead-ends, coverage, obvious-link ratio) — that's [constellation.md](constellation.md).
- Truth of the underlying facts — the grounding pipeline ([ADR 0005](../../docs/adr/0005-closed-book-grounding.md)).
