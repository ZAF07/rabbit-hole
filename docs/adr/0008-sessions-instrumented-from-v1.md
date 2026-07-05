# Sessions are persisted and instrumented from V1; personalization consumes them in Phase 2

A [Session](../../CONTEXT.md) — the user's path through the Content Graph — is a **persisted, instrumented entity from V1**, even though the V1 *experience* is globally curated and personalizes nothing. The stored path is the raw substrate the **Tapestry** (the user's Personal Knowledge Graph) is built from — shown to the user in V1, and read by personalization in Phase 2.

**The session model being recorded:**
- **Shape:** linear path with **backtracking** — the user pulls one Connection at a time, but can step back up a stack to try a different fork. Not free-roam.
- **Boundary:** a Session (the analytics window) ends on a **hybrid** rule — inactivity timeout (~30 min) *or* explicit app close, whichever first.
- **Depth = distinct Pieces visited** (deduped). Backtracking to re-read doesn't inflate it; pulling a new fork does. Depth measures ground covered, not fidgeting.

**Two rules make the decision concrete:**

1. **Record ≠ personalize.** V1 stores every Session path but personalizes nothing — the Daily Feature is the same for everyone ([experience.md](../experience.md) V1 scope). Capturing the signal is *instrumentation*, not personalization; the two are decoupled so the experience stays global while the substrate accumulates. The line is not two entities but **one asset with a deferred capability**: V1 **builds and shows** the Tapestry ([ADR 0009](0009-retention-earned-not-gamified.md)); **acting on** it to tailor what's surfaced is the Phase-2 use.
2. **The path outlives the analytics Session.** The durable path (current Piece + backtrack stack) is persisted independently and is **resumable across app opens** in V1. The Daily Feature remains the front door / heartbeat, with a "continue your thread" affordance when a resumable path exists. Resuming after a timeout gap simply begins a new Session that continues the same path.

**Why:**
- **History can't be backfilled.** A Tapestry that first ships in Phase 2 with zero backlog cold-starts blind. Recording paths from day one means personalization launches with real per-user curiosity history instead of nothing.
- **Honest metric + standard UX.** Separating the durable path from the time-bounded Session keeps *depth* an honest engagement measure while still supporting the resume behavior users expect.
- **House pattern.** Same discipline as the grounding ledger ([ADR 0005](0005-closed-book-grounding.md)) and the verdict corpus ([ADR 0004](0004-human-ratified-learning-loop.md)): instrument now, act deliberately later, human-in-the-loop. Never act on the signal automatically just because it is captured.

**Trade-off:** persisting per-user paths introduces user-identity and user-data surface (accounts, storage, and eventually privacy/consent) earlier than a purely stateless V1 would. Accepted — it is standard product instrumentation, and the Tapestry is a core Phase-2 bet that is worthless without backlog.

**Consequence:** V1 requires **per-user identity and path persistence** on the consumption side, even though it exposes no personalization. Sessions and the Personal Knowledge Graph are **consumption-side** entities derived from user behavior; they are unrelated to the generation/consumption boundary ([ADR 0006](0006-generation-and-consumption-are-separate.md)) — generation never sees them. When the boundary is that Content Graph, user-behavior data sits wholly downstream of it.
