# Anti-Slop Guardrails — Constellation-level checks

Applied by **Constellation QA** (Stage 6) over a whole run's output. Two tiers: **hard invariants** (the deterministic outcome contract — binary, all must hold, or the run fails) and **journey-coherence checks** (Reviewer-judged; softer, loop-or-flag).

## Tier 1 · Hard invariants — the outcome contract
Every run over a Theme Brief must satisfy **all** of these. Binary. A miss **fails the run**, not a soft warning. This is the concrete form of the "deterministic outcome" required in [content-harness.md](../../docs/content-harness.md) — the guarantee holds *by construction*, not by a lenient judge's mercy.

**Completeness**
- **I1 · Count.** Piece count meets the Theme Brief target.
- **I2 · Required fields.** Every Piece has `id`, `title`, `topics[]`, `teaser`, `readTimeMin`, `body` (≥1 Content Block), and passed [piece.md](piece.md).
- **I3 · Topic coverage.** The constellation spans the Brief's target Topics (e.g. 4–5).

**Graph integrity**
- **I4 · Zero dead ends.** Every Piece has ≥1 outbound Connection.
- **I5 · Resolvable.** Every Connection resolves to a real Piece; every hook is present, per-origin, and passed [connection.md](connection.md).
- **I6 · ≥1 cross-Topic per Piece.** Every Piece has at least one outbound Connection whose destination sits in a **different Topic** — the structural *"everything connects"* guarantee. Designed in by the Architect at plan time, verified here.
- **I7 · Connected.** The constellation is a single connected graph — no isolated island Piece unreachable from the rest.

**Grounding**
- **I8 · Grounded.** Every Piece has a complete grounding ledger; no ungrounded load-bearing claim ([ADR 0005](../../docs/adr/0005-closed-book-grounding.md)).

## Tier 2 · Journey-coherence — Reviewer-judged
Softer, holistic — the Reviewer flags/loops rather than hard-failing. **FAIL-if** style:
- **J1 · Not all-obvious.** FAIL if the graph is entirely in-Topic next-steps with no real cross-Topic *surprise density* (I6 guarantees ≥1 each; J1 guards the overall texture).
- **J2 · No near-duplicates.** FAIL if two Pieces cover materially the same ground.
- **J3 · Entry-worthy nodes exist.** FAIL if no Piece works cold as a Daily Feature — a strong standalone `teaser`, no assumed prior Piece.
- **J4 · Pacing spread.** FAIL if every Piece is uniformly dense/long; a constellation needs range.
- **J5 · Coherent theme.** FAIL if the Pieces don't cohere as a themed set — the Brief's through-line should be visible without being repetitive.

## Not judged here
- Individual Piece prose — [piece.md](piece.md).
- Individual Connection/hook — [connection.md](connection.md).
- Truth — the grounding pipeline ([ADR 0005](../../docs/adr/0005-closed-book-grounding.md)).
