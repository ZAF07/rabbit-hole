# Consumer Experience — Design Notes

Living design record for the reading/traversal side of the app (what users actually *do*). Sibling to [content-harness.md](content-harness.md) (the generation mechanism). The two are **separate worlds** joined only by the Content Graph — see [ADR 0006](adr/0006-generation-and-consumption-are-separate.md). This doc never references runs, constellations, or how content was made; it only knows Pieces and Connections.

Uses the internal vocabulary; UI labels are the branded presentation layer (see [CONTEXT.md](../CONTEXT.md) / [ADR 0001](adr/0001-decouple-internal-and-ui-vocabulary.md)).

## The north star
The user should *see how things in the world connect*. Every design choice serves that feeling.

## The core loop
1. **Open the app** → the user lands on one Piece (the **Daily Feature** front door). They see its **title, Topic, and hook** — and optionally a peek at the Pieces it Connects to (their Topics + hooks), so the branching is visible up front.
2. **Read the Piece.**
3. **At the end** → they're presented with the **connected Pieces** they can *"pull the thread on"* — each shown as its destination Topic + hook.
4. **Pull a thread** → they're now reading that Piece. Return to step 2.

That traversal — enter at a Piece, pull Connection after Connection — is a **Session**. It reads only Pieces and Connections; it has no knowledge of runs or constellations.

## V1 scope — firm out the architecture before personalization

- **Global content, not personalized surfacing.** The Daily Feature is editorially chosen — the same for everyone. **Personalizing what gets surfaced** (reading the Tapestry to tailor the feed / recommend Connections) is **Phase 2**.
- **But the Tapestry ships in V1.** Building and showing a User *their own* trail (their Personal Knowledge Graph, from their Session paths) is not personalization — it surfaces their own history, not a tailored feed. It's a V1 retention driver (see Retention below). **One asset, two uses:** shown in V1, personalized-from in Phase 2.
- **Rationale:** cleanest possible retention test; the idea doc sequences personalized *surfacing* to Phase 2 and names premature personalization a risk. Personalized surfacing amplifies a working loop; it can't create one. The Tapestry, by contrast, deepens investment without prejudging what to recommend.

## The Piece consumer schema (locked — Q9)

What a Piece must carry so the app can render and traverse it — the **read side of the Content Graph boundary**. Nothing generation-only crosses it ([ADR 0006](adr/0006-generation-and-consumption-are-separate.md)).

```
Piece {
  id                          // Connection targets resolve to this; Session path history
  title
  topics[]                    // Topic tag(s) — the classification signal shown in UI
  teaser                      // standalone lure — shown when this Piece is an ENTRY POINT
  readTimeMin                 // "6 min" expectation-setter shown before a pull
  body: Block[]               // ordered list of content blocks (see below)
  connections[]               // outbound threads — each { toPieceId, hook }
}
```

- **`connections[]`** carries only `toPieceId` + `hook`. The renderer joins `toPieceId` to the target's `title` + `topics` to build the preview card. The **`hook` is per-origin** and lives on the Connection — the same destination pitched differently depending on where you came from ([CONTEXT.md](../CONTEXT.md)).
- **`teaser` vs `hook` (locked).** A Piece carries its own `teaser` for when it is an entry point with **no incoming Connection** (Daily Feature / cold-start surfaces). Hooks stay on Connections. Two distinct lures, never conflated.
- **Not present, by design:** `runId`, `constellationId`, grounding ledger, theme brief — all upstream ([ADR 0006](adr/0006-generation-and-consumption-are-separate.md)). A `runId` may ride along on a Piece for debug provenance, but consumption never keys off it.

### `body` is a list of Content Blocks (locked — format (b))

Structured blocks over freeform markdown, because "highly visual / magazine-clean" is a core pillar markdown can't guarantee, blocks give the generation harness a **checkable output contract** (Stage 4/6 QA can assert visual rhythm), and visual media becomes **first-class** rather than smuggled into prose.

The vocabulary is **small and fixed** — every block type is a renderer commitment *and* a QA rule. V1 set:

| Block | Kind | Key fields |
| --- | --- | --- |
| `heading` | text | `text`, `level` |
| `paragraph` | text | `text` (inline emphasis allowed) |
| `pull-quote` | text | `text`, optional `attribution` |
| `stat-callout` | text | `value`, `label` |
| `image` | visual · **V1-deferred** | `src`, `alt`, `caption`, `credit` |
| `gif` | visual · **V1-deferred** | `src`, `alt`, `caption` (motion; autoplay muted, loops) |
| `diagram` | visual · **V1-deferred** | explanatory schematic — spec settled when visuals arrive |

Visual blocks (`image`, `gif`, `diagram`) are **reserved as first-class slots but not populated in V1** — Pieces ship text-only. When they arrive they are *sourced or data-grounded, never fabricated* (no AI-generated imagery). See [ADR 0007](adr/0007-visual-provenance-sourced-or-data-grounded.md).

## Session mechanics

A Session is shaped as a **linear path with backtracking** (decision (b)):
- **Forward** — the user pulls one Connection at a time; a single advancing thread.
- **Backtrack** — they can step back up the path (a stack) to try a *different* outbound Connection from a Piece already visited. A rejected fork never kills the journey.
- **Not** free-roam — no arbitrary jumping across the graph. (A map view is a possible Phase-2 flourish.)

**The path is stored (path memory).** The ordered list of Pieces a Session visits is persisted, not ephemeral.
- **Why it's crucial:** the stored path is the **raw substrate for the Tapestry** (the Personal Knowledge Graph). The Tapestry is *shown* in V1; personalizing from it is Phase 2 — but either way the history must be captured from day one, or the Tapestry cold-starts with nothing.
- **Recording ≠ personalizing.** V1's *experience* stays globally curated (same Daily Feature for everyone). Storing paths is instrumentation, not personalization — the same "capture the signal now, act on it deliberately later, human-in-the-loop" pattern as the grounding ledger and the verdict corpus.

**Boundary & metric (locked — [ADR 0008](adr/0008-sessions-instrumented-from-v1.md)):**
- **What ends a Session:** hybrid — an inactivity timeout (~30 min) *or* explicit app close, whichever first. A generous gap keeps a real-life interruption from shattering one journey into fragments.
- **Depth = distinct Pieces visited** (deduped). Backtracking to re-read a Piece already seen doesn't inflate depth; popping back to pull a *new* fork does. Depth measures the ground the curiosity covered, not fidgeting. (Total pulls may be a secondary metric later.)
- **Resumable across app opens (V1).** The durable path outlives the analytics Session: it is persisted and restorable (current Piece + backtrack stack). On open, the **Daily Feature stays the front door / heartbeat**, with a prominent "continue your thread" entry when a resumable path exists. Resuming after a timeout gap begins a *new* Session that continues the same path.
- **Implication:** V1 needs **per-user identity + path persistence** on the consumption side — even though it personalizes nothing yet.

## Retention — earned, never gamified

Retention comes from curiosity and personal investment, never compulsion. **No streaks, badges, points, or leaderboards — ever, at any phase** (not deferred: *rejected outright*). See [ADR 0009](adr/0009-retention-earned-not-gamified.md).

Three intrinsic drivers:

1. **Direct — the daily curiosity hook (V1).** One dignified daily notification teasing the Daily Feature's real hook (*"Why does the US Navy still run on 1970s code?"*), held to the same anti-slop / anti-clickbait bar as in-app hooks — a genuine open loop the Piece closes. Never a nag, never bait-and-switch.
2. **Indirect — the Tapestry (V1).** Users return because they are *building a personal intellectual trail they own* — their Personal Knowledge Graph, the growing graph of Pieces read + Connections pulled (the per-user subgraph of the Content Graph induced by Session paths). Investment, not compulsion. **Free in V1; a candidate premium feature later.**
3. **Indirect — bounded depth journeys / Arcs (V2).** Finite, curated, finishable arcs with a stated learning goal — *"5 Pieces to understand how modern maps work,"* *"7 Pieces to why semiconductors are geopolitically critical."* People return for a **finishable intellectual object**. Infinite content is cheap; completion of understanding is valuable. The deliberate opposite of infinite scroll.

## The Tapestry (V1)

The user's Personal Knowledge Graph made visible. Built as the **union of the user's Session paths** (deduped): every distinct Piece they've read is a node, every Connection they pulled is an edge — a per-user subgraph of the Content Graph. One asset, shown here in V1; personalized-*from* in Phase 2 ([ADR 0009](adr/0009-retention-earned-not-gamified.md)).

**Shape (locked):**
- **Visual node-graph** — Pieces = nodes, Connections = edges, **colored/clustered by Topic**; grows as the user traverses. The payoff is *"the web of understanding I've built."* (Rendering the user's own real data — no fabrication concern; [ADR 0007](adr/0007-visual-provenance-sourced-or-data-grounded.md) governs imagery *inside* Pieces, not this.)
- **Navigable** — tapping a node revisits that Piece (reread, or pull a different thread from it). The Tapestry is both a trophy *and* a re-entry point into the Content Graph, never decoration.
- **First-run** — starts sparse, seeded by the Daily Feature as the first node, and thickens every Session.

**Frontier hints (V1.1 / V2).** Beyond the visited subgraph, hint at the **unpulled Connections** dangling off visited Pieces — threads not yet followed. A genuine curiosity engine, with the intended microcopy: **"you're one pull from something new."** (That branded line lives in the presentation vocabulary module when built — [ADR 0001](adr/0001-decouple-internal-and-ui-vocabulary.md).) Deferred after the base Tapestry ships; adds rendering complexity the core doesn't need.

## Open / next

The **consumption side is now specified for V1** — Content Graph boundary, Piece + Content Blocks, Session model, retention, Tapestry. The remaining design surface is mostly the **generation harness authoring detail**:

- Agent roster & per-agent guardrail files (Architect · Researcher · Writer · Editor · Weaver · Reviewer · Distiller) — see [content-harness.md](content-harness.md).
- The actual anti-slop rubric (`guardrails/piece.md`) + first exemplars.
- Editorial DNA gate template (voice, quality bar, banned-filler list).
- Dual-runtime (Claude Code skills/agents ↔ LangGraph) parity.
- Graduate the finalized pipeline architecture to an ADR.

### Deferred to future phases
- **Visuals** — stance locked ([ADR 0007](adr/0007-visual-provenance-sourced-or-data-grounded.md)): sourced or data-grounded, never fabricated, split by block kind. V1 ships text-only with visual slots reserved. Revisit post-V1: the visual grounding ledger, asset-sourcing stage, and `diagram` spec.
- **Frontier hints** — the Tapestry's unpulled-Connection curiosity layer + *"you're one pull from something new."* V1.1 / V2.
- **Personalized surfacing** — reading the Tapestry to tailor the feed. Phase 2. (The Tapestry itself ships in V1.)
- **Arcs** (bounded depth journeys) — the V2 finishable-journey object; needs an authoring/curation model. See [ADR 0009](adr/0009-retention-earned-not-gamified.md).
