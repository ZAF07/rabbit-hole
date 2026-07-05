# PRD: The Consumption App — reader backend

Status: ready-for-agent
Feature: consumption-app
Depends on: `content-graph` (reads Pieces / Connections through the `ContentGraphRepository` read surface)

> This PRD implements the consumption subsystem: the reader experience of [experience.md](../../docs/experience.md). It reads **only** Pieces and Connections from the Content Graph and knows nothing about runs, constellations, or how content was made ([ADR 0006](../../docs/adr/0006-generation-and-consumption-are-separate.md)).

## Problem Statement

A curious adult opens their phone with ten idle minutes and wants to be *taken somewhere interesting* — pulled into a genuinely fascinating idea, then handed a surprising thread to the next one, and the next, until they surface with something they can't wait to tell someone tonight. The feeling the product sells is **"see how things in the world connect."** None of it exists yet. There is (will be) a corpus of Pieces joined by Connections, but no experience that lets a reader **enter, read, follow Connections, wander and backtrack, leave, and come back to a growing trail they own**. Without that loop — and without capturing the reader's path from day one — there is no product to retain anyone, and the asset that makes retention *earned* (their Personal Knowledge Graph) can never be built later because its raw substrate was never recorded.

## Solution

A Python + Postgres **consumption backend** (ports-and-adapters) that reads only Pieces and Connections from the Content Graph and delivers the core loop of [experience.md](../../docs/experience.md):

1. **Open** → land on the **Daily Feature** (the editorially-chosen front door, same for everyone in V1): title, Topic, hook, optionally a peek at what it Connects to.
2. **Read** the Piece, rendered from its ordered **Content Blocks**.
3. **At the end** → see the **connected Pieces** as "pull this thread" cards (destination Topic + per-origin hook).
4. **Pull a thread** → now reading that Piece. Repeat. **Backtrack** up the path to try a different fork.

The reader's **path is persisted from V1** — the raw substrate for the **Tapestry** (their Personal Knowledge Graph): a navigable visual node-graph of Pieces read + Connections pulled, colored by Topic, shown as a V1 retention driver. V1 needs **per-user identity + path persistence** even though it personalizes nothing yet — recording ≠ personalizing ([ADR 0008](../../docs/adr/0008-sessions-instrumented-from-v1.md)). Retention is **earned, never gamified**: one dignified daily curiosity hook; the Tapestry; (Arcs are V2). **No streaks, badges, points, or leaderboards — ever** ([ADR 0009](../../docs/adr/0009-retention-earned-not-gamified.md)). All branded strings ("Thread", "Tapestry", …) render from the single **presentation vocabulary module**; the domain and API use internal terms only ([ADR 0001](../../docs/adr/0001-decouple-internal-and-ui-vocabulary.md)).

## User Stories

*Actor: the **curious reader** (a User), unless noted. Also the **developer** building the backend and the **product/editor** shaping the front door.*

**The core loop**
1. As a reader, I want to open the app onto a single compelling Daily Feature, so that I always have an obvious, high-quality place to start.
2. As a reader, I want to see a Piece's title, Topic, and hook before I commit, so that I know why it might be worth my next five minutes.
3. As a reader, I want to optionally peek at the Pieces a Piece Connects to (their Topics + hooks) up front, so that the branching is visible before I even start reading.
4. As a reader, I want to read a Piece rendered as clean, ordered Content Blocks, so that it feels magazine-clean, not like a wall of text.
5. As a reader, I want a "6 min" read-time expectation before I open a Piece, so that I can decide if I have time now.
6. As a reader, I want to reach the end and be offered the connected Pieces as "pull this thread" cards — each showing the destination's Topic and a hook written *for this jump* — so that the next step is irresistible and specific.
7. As a reader, I want to pull a thread and immediately be reading the destination Piece, so that following curiosity is one tap, with no friction.
8. As a reader, I want a Piece I land on cold (the Daily Feature) to show its own **teaser**, while onward jumps show the Connection's **hook**, so that entry and continuation each have the right lure.

**Wandering & backtracking**
9. As a reader, I want to step back up my path to a Piece I already read, so that a fork I regret doesn't end my journey.
10. As a reader, I want to pull a *different* Connection from a Piece I backtracked to, so that I can explore an alternative branch.
11. As a reader, I want backtracking to feel like a stack (return the way I came), so that my journey stays coherent rather than teleporting me around the graph.
12. As a reader, I do **not** want arbitrary free-roam jumps across the whole graph in V1, so that the experience stays a guided journey rather than a search box.

**Leaving & coming back**
13. As a reader, I want my journey to survive a real-life interruption (a ~30-minute gap doesn't shatter it), so that stepping away doesn't cost me my place.
14. As a reader, I want to reopen the app and find a prominent "continue your thread," so that I can resume exactly where I was (current Piece + my backtrack stack).
15. As a reader, I want the Daily Feature to still greet me each day as the heartbeat, even when I have a resumable thread, so that there's always something fresh *and* a way back in.
16. As a reader, I want one dignified daily notification teasing the day's real hook (never a nag, never bait-and-switch), so that I'm reminded to be curious without being manipulated.

**The Tapestry (their own trail)**
17. As a reader, I want to see the growing web of everything I've read — Pieces as nodes, the Connections I pulled as edges, clustered by Topic — so that I feel I'm building something that's mine.
18. As a reader, I want to tap a node in my Tapestry to revisit that Piece (reread it, or pull a different thread from it), so that the trail is a re-entry point, not just a trophy.
19. As a reader, I want my Tapestry to start from my very first Daily Feature and thicken every session, so that even day one shows a seed that visibly grows.
20. As a reader, I want re-reading a Piece I've already seen **not** to inflate anything — my trail reflects distinct ground covered, not fidgeting — so that the Tapestry stays an honest map of my curiosity.

**Vocabulary, boundary, identity (developer / product)**
21. As the product, I want every user-facing label to come from one presentation vocabulary module keyed by internal term, so that we can rebrand or rename the app by editing one file, with no data-model change ([ADR 0001](../../docs/adr/0001-decouple-internal-and-ui-vocabulary.md)).
22. As a developer, I want the backend to read only Pieces and Connections (never run id or constellation) from the Content Graph, so that the boundary to generation cannot leak into the experience ([ADR 0006](../../docs/adr/0006-generation-and-consumption-are-separate.md)).
23. As a developer, I want per-user identity and durable path storage from V1, so that the Tapestry has real history to render and Phase-2 personalization has a substrate to read.
24. As the product, I want the same Daily Feature served to everyone in V1 (global, editorially chosen — no personalized surfacing), so that we test the core loop cleanly before amplifying it.
25. As an analyst, I want **Session depth = distinct Pieces visited** recorded, so that we measure the ground a reader's curiosity actually covered.

## Implementation Decisions

**Modules built**
- A `consumption` **domain / application-service** package — the reader use-cases: `GetDailyFeature`, `ReadPiece`, `PullConnection`, `Backtrack`, `ResumeSession`, `GetTapestry`. Framework-free; internal vocabulary only.
- **Ports:** the `ContentGraphRepository` **read surface** (from `content-graph`); a `SessionRepository` (durable path + backtrack stack + analytics-Session boundary); a `UserRepository` / identity port.
- **Adapters:** Postgres for the user/session/path tables; the shared Content Graph read adapter.
- A **presentation vocabulary module** — the app's only source of branded strings, an i18n-style bundle keyed by internal term (`vocab.piece.one → "Thread"`, `vocab.interestProfile → "Tapestry"`, …). UI renders from it; domain/API never import it ([ADR 0001](../../docs/adr/0001-decouple-internal-and-ui-vocabulary.md)).

**Session model** ([ADR 0008](../../docs/adr/0008-sessions-instrumented-from-v1.md))
- Shape: **linear path with backtracking** — a single advancing thread plus a stack to step back and try another fork. Not free-roam.
- **Path is persisted** (ordered list of visited Pieces) — the raw substrate for the Tapestry. Recording ≠ personalizing.
- **Depth = distinct Pieces visited** (deduped); re-reading doesn't inflate it; popping back to pull a *new* fork does.
- **Boundary:** hybrid — inactivity timeout (~30 min) *or* explicit app close, whichever first. The durable path **outlives** the analytics Session and is **resumable** (current Piece + backtrack stack). Resuming after a timeout gap starts a *new* Session continuing the same path.

**The Tapestry** ([ADR 0009](../../docs/adr/0009-retention-earned-not-gamified.md))
- The **deduped union of the user's Session paths** — a per-user subgraph of the Content Graph: nodes = distinct Pieces read, edges = Connections pulled, colored/clustered by Topic.
- **Navigable** (tap a node → revisit that Piece); **seeded first-run** by the Daily Feature; thickens each Session.
- One asset, two uses: **shown** in V1; **personalized-from** in Phase 2 (same entity, not a new one).

**Rendering & retention**
- A Piece's `body` renders from ordered Content Blocks; V1 renders the **text kinds only** (visual kinds reserved but empty — [ADR 0007](../../docs/adr/0007-visual-provenance-sourced-or-data-grounded.md)).
- Connection preview cards join `toPieceId` → destination `title` + `topics` and show the Connection's `hook`.
- Retention drivers: the **daily curiosity hook** (one, dignified, anti-clickbait, held to the same bar as in-app hooks) and the **Tapestry**. **No streaks / badges / points / leaderboards — rejected outright, at every phase.**

## Testing Decisions

**What a good test is here:** it drives the reader **use-cases through their public interface** and asserts observable behavior of the loop — never storage internals. The `ContentGraphReader` is backed by an **in-memory fake seeded with a fixture constellation**; the user/session ports are in-memory fakes — so the whole loop is testable fast and offline.

- **The seam — the application-service boundary.** With a fixture constellation loaded:
  - `GetDailyFeature` returns an entry-worthy Piece with its `teaser`.
  - `ReadPiece` returns ordered Content Blocks + connection previews (each with `hook` and joined destination title/Topics).
  - `PullConnection` advances the path to the destination and appends it.
  - `Backtrack` pops to the prior Piece and permits pulling a *different* outbound Connection.
  - **Depth** counts distinct Pieces — re-reading a seen Piece does not increase it; pulling a new fork does.
  - `ResumeSession` restores current Piece + backtrack stack after a close.
  - `GetTapestry` returns the deduped union of paths, edges = Connections pulled, clustered by Topic; seeded by the first Daily Feature.
- **Session boundary:** inactivity ≥ ~30 min or app close ends the analytics Session; resuming after the gap begins a **new** Session continuing the **same** path.
- **Boundary guard:** read models expose no `run_id` / constellation; a test asserts the reader never depends on generation-only fields ([ADR 0006](../../docs/adr/0006-generation-and-consumption-are-separate.md)).
- **Postgres adapters** (user / session / path) reuse the **contract-test-against-Docker** pattern established in `content-graph`.
- **Prior art:** the in-memory fake + contract-test pattern from `content-graph`.

## Out of Scope

- **Personalized surfacing** — reading the Tapestry to tailor the feed / recommend Connections is **Phase 2**. (The Tapestry itself ships in V1; it just drives nothing yet.)
- **Frontier hints** — the Tapestry's unpulled-Connection layer and the *"you're one pull from something new"* microcopy — **V1.1 / V2**.
- **Arcs** — bounded, finishable journeys with a learning goal — **V2**; authoring/curation model undesigned ([ADR 0009](../../docs/adr/0009-retention-earned-not-gamified.md)).
- **Visual block rendering** — text-only V1; visual slots reserved but empty ([ADR 0007](../../docs/adr/0007-visual-provenance-sourced-or-data-grounded.md)).
- **Paywall / premium** — the Tapestry is free in V1 (a candidate premium feature later).
- **Gamification of any kind** — not deferred, *rejected* ([ADR 0009](../../docs/adr/0009-retention-earned-not-gamified.md)).
- **The client UI framework and the app's final name** — a later decision; this PRD is the consumption backend + its API. A map/free-roam view is a possible Phase-2 flourish.
- **Anything generation** — the pipeline, grounding, constellation shape.

## Further Notes

- North star: *the reader should see how things in the world connect* — every choice serves that feeling ([experience.md](../../docs/experience.md)).
- V1 deliberately separates **recording** (paths persisted from day one) from **acting** (personalization in Phase 2) — the same "capture the signal now, act deliberately later" pattern as the harness's grounding ledger.
- Depends on `content-graph` only for the read surface; shares no code with `generation-harness`.
