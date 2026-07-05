# The publish gate: re-wire and re-QA the approved subset

Constellation QA (Stage 6) verifies the outcome contract **I1–I8** over the **whole** constellation. But the human gate ([ADR 0004](0004-human-ratified-learning-loop.md)) approves Pieces **one at a time** and may **reject** some. The approved subset is therefore a *different graph* than the one QA validated: a survivor whose only outbound Connection pointed at a rejected Piece is now a **dead end (I4)**; the graph may **fragment (I7)**. Because the Content Graph is the **published** store consumption reads directly, such a break is one a real reader would hit — the exact "smart and trustworthy" failure the product cannot afford.

## Decision

Publishing is **not** "INSERT the approved Pieces." After the human's verdicts, the harness **re-runs Weaver + Reviewer over the approved subset**, and writes to the Content Graph **only if that re-QA passes on the survivors**:

1. Collect the approved Pieces (rejected ones removed).
2. **Weaver re-wires** the survivors — re-checking that every survivor still has ≥1 outbound Connection (I4), every Connection still resolves inside the surviving set (I5), every Piece still carries ≥1 cross-Topic Connection (I6), and the graph is still connected (I7). Connections into rejected Pieces are dropped; a survivor left short of a needed Connection gets one re-authored where the plan allows.
3. **Reviewer re-QAs** the survivor subset against [`constellation.md`](../../harness/guardrails/constellation.md) Tier-1.
4. A survivor that **cannot** be made contract-valid (e.g. a now-orphaned Piece with no honest Connection to offer) is **flagged back to the human** — re-wire, hold, or cut — never silently published into a broken state.
5. Only the validated survivor set is written, as one publish.

## Why
- **The invariant must hold on what *ships*, not on what QA first saw.** I4/I7 are promises to the reader; they must be true of the **published** graph after human edits, or they are theatre.
- **Human rejection is expected, not exceptional** — the human is the arbiter and *will* cut Pieces ([ADR 0004](0004-human-ratified-learning-loop.md)). The publish path must be correct under partial approval **by construction** — the same "guarantee by construction" logic as plan-first and closed-book.

## Trade-off
A rejection triggers a re-wiring + re-QA pass (and possibly one more small human touch to place a replacement Connection) instead of a bare insert — heavier, and it can delay shipping a survivor until its neighbourhood is re-validated. Accepted. Two alternatives were rejected: **all-or-nothing** (a rejection sends the whole constellation back) is too coarse — one weak Piece should not block 29 good ones; **per-Piece publish with incremental edge-repair** has too many moving parts to keep I4/I7 honest as the graph mutates one Piece at a time.

## Consequence
The write tool's contract is **"publish = re-wire the survivors → re-QA Tier-1 → atomic write of the validated set,"** not a raw insert. The **Weaver and Reviewer therefore run in two modes**: the in-run pass over the planned constellation, and the **post-approval pass over the approved subset**. Governs generation only; what crosses the [ADR 0006](0006-generation-and-consumption-are-separate.md) boundary is still just Pieces, Connections, and Topics — now guaranteed contract-valid **as published**.
