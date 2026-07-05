# Anti-Slop Guardrails — Piece-level checks

The concrete, checkable failure-mode list a **Piece** must pass. Applied by the machine-QA judge (Stage 4) as a **filter** — it loops the Editor until pass or the QA budget is spent. It is **not** the arbiter; the human is ([ADR 0004](../../docs/adr/0004-human-ratified-learning-loop.md)). Derived from the spirit in [`../editorial/dna.md`](../editorial/dna.md).

**Rules of the rubric:**
- Every check is **binary or near-binary with a concrete definition** — never "rate 1–10." Self-lenient scores are exactly how slop passes.
- Read each as **FAIL if …**. Any FAIL → back to the Editor with the specific violation quoted.
- **"Is it true" is not here.** Grounding is a separate judgment ([ADR 0005](../../docs/adr/0005-closed-book-grounding.md)); truth and slop are never merged into one score.

## A · The opening (first ~3 sentences)
- **A1 · Concrete open.** FAIL if it opens with a definition, a dictionary move, or throat-clearing instead of a scene, a person, a moment, or a startling concrete fact.
- **A2 · No throat-clearing.** FAIL on any warm-up phrase ("In today's world", "Have you ever wondered", "Since the dawn of…", "More than ever before").
- **A3 · Reason-to-care by sentence 3.** FAIL if the reader hasn't hit tension, stakes, or surprise within three sentences.

## B · Density & specificity (every paragraph)
- **B1 · A specific detail per paragraph.** FAIL if any paragraph lacks a concrete, checkable detail — a name, date, number, object, or event. (A brief one-line transition between beats is fine; the target is *no full paragraph of pure abstraction*.) Kept strict — abstraction-drift is a primary slop texture.
- **B2 · No padding.** FAIL if a sentence could be cut with no loss of meaning (restatement, connective mush, hedging).
- **B3 · Show the number.** FAIL if a magnitude word ("huge", "vast", "tiny") stands where a concrete figure or comparison exists and was omitted.

## C · The reframe (the "holy shit")
- **C1 · Delivers a non-obvious payoff.** FAIL if the Piece delivers neither (a) a genuine **reframe** — a surprising connection, inversion, or hidden-cause reveal — **nor** (b) a genuinely **novel, vivid understanding** the reader almost certainly didn't have before. Flat summary of already-known facts fails; vivid illumination passes even without an inversion. *(Calibrated down from "reframe required in every Piece" — some great Pieces illuminate without inverting.)*
- **C2 · Earned, not announced.** FAIL if the reframe is asserted ("Surprisingly, …") rather than built to and discovered.
- **C3 · Real, not fake insight.** FAIL if the "insight" is a truism, is circular, or would not actually surprise a curious adult.

## D · Slop tells (the instant-detect list)
- **D1 · No listicle scaffolding.** FAIL on "N reasons why" / "here are the ways" prose skeletons. (Structured Content Blocks are fine; a listicle *argument shape* is not.)
- **D2 · No hedging mush.** FAIL on "many experts believe", "it could be argued", "some say", "arguably" used to dodge a claim. Ground it or cut it.
- **D3 · No banned-filler phrase.** FAIL on any phrase in the banned list below.
- **D4 · No AI-summary cadence.** FAIL if paragraphs are uniform, evenly weighted, and list-like (the tell of generated prose) instead of rhythmically varied.
- **D5 · No empty conclusion.** FAIL on "In conclusion", "All in all", "At the end of the day" wrap-ups that merely restate.
- **D6 · No definitional frame.** FAIL on Wikipedia's signature "X is a Y that…" used as a structural crutch to open a section.
- **D7 · No both-sides mush.** FAIL on false balance that refuses a position the sources support ("there are many viewpoints", "opinions differ") to avoid committing.
- **D8 · No over-explaining the obvious.** FAIL if the Piece belabors what a curious adult already knows — padding disguised as accessibility.
- **D9 · No adjective stacking.** FAIL on strings of empty intensifiers ("incredibly fascinating, truly remarkable, absolutely stunning").

## E · Payoff & exit
- **E1 · Dinner-party test.** FAIL if the reader finishes with nothing specific they'd want to *say* to another person tonight.
- **E2 · Ends on a doorway.** FAIL if the close doesn't open outward — curiosity toward a connected thread (this feeds the Connection hook), per the Voice Profile.

## F · Voice conformance
- **F1 · Matches the active Voice Profile.** FAIL if register, POV, or moves violate [`../editorial/voices/`](../editorial/voices/) (default `narrative-nonfiction`). The profile's **Don'ts are hard fails.**

## Banned-filler phrases (check D3)
**This list is deliberately incomplete — that is by design, not a coverage gap.** It seeds; the [learning loop](../../docs/content-harness.md) grows it from real human deletions (edit-diffs → distillation → here, human-ratified). Phrases not yet listed are still caught generically by D1–D9. FAIL on any:

- "In today's world" / "In an increasingly ___ world"
- "Have you ever wondered" / "Picture this"
- "Since the dawn of time" / "Throughout history"
- "It's no secret that" / "Needless to say"
- "game-changer" / "revolutionary" / "cutting-edge" / "the world of ___"
- "buckle up" / "let that sink in" / "little did they know"
- "the rest is history" / "stood the test of time"
- "at the end of the day" / "when all is said and done"
- "delve" / "in the realm of" / "a testament to" / "plays a crucial role"
- "not only … but also" as a default connective

*(Brand-metaphor words — thread, weave, spool, tapestry, unspool — are **not** banned here; they belong to the UI presentation layer, not Piece prose.)*

## What this rubric does NOT judge
- **Truth / grounding** — separate pipeline ([ADR 0005](../../docs/adr/0005-closed-book-grounding.md)).
- **The final quality verdict** — the human is the arbiter ([ADR 0004](../../docs/adr/0004-human-ratified-learning-loop.md)). This rubric is a bouncer that keeps junk out of the human's queue, not the editor-in-chief.
