# Visuals are sourced or data-grounded, never fabricated (and deferred in V1)

Visual content obeys the same integrity discipline as text. Two rules, plus a scope decision.

**Rule 1 — No fabricated photorealistic imagery, ever.** An AI-generated "photo" is the visual analogue of AI slop, and worse than the textual kind: a fabricated image *actively misleads* (wrong subject, wrong era, an invented "photograph" of a real event). This is the pixel-side twin of closed-book grounding ([ADR 0005](0005-closed-book-grounding.md)) — the product's value is being perceived as smart and trustworthy, and one fake image destroys that faster than one wrong sentence.

**Rule 2 — Provenance splits by block kind.** Each visual [Content Block](../../CONTEXT.md) carries its own grounding discipline, mirroring the fact-grounding pipeline:

| Block | Provenance model | Grounding discipline |
| --- | --- | --- |
| `image` (photo) | **Sourced real asset** — archival, licensed, Creative Commons, primary-source. Never generated. | Real origin, correct + non-misleading caption, license/credit recorded, not decontextualized — a **visual grounding ledger** parallel to the claim ledger. |
| `gif` | **Sourced real footage/animation** (same rules as `image`). | Same. |
| `diagram` | **Generated — but only as a deterministic render over data already in the vetted claim pack.** Truth drawn as a picture, not fabricated imagery. | Underlying numbers are already vetted by Stage 2; the render only visualizes them; layout is human-approved. |

AI image-generation is confined *at most* to clearly-non-photographic explanatory illustration, human-approved — and is **banned outright in V1**.

**Scope — V1 ships text-only.** The `image` / `gif` / `diagram` block types stay **reserved as first-class slots** in the Content Block vocabulary, but are **not populated in V1**. Pieces ship as text blocks only. Visuals are deferred to a future phase. The generation harness therefore remains text-only for V1, consistent with [content-harness.md](../content-harness.md).

**Why:**
- **Anti-slop is the moat**, and the moat has to hold for pixels too — otherwise the trust the text pipeline earns leaks out through the images.
- **Deferring proves the right thing first.** V1's job is to validate the reading/traversal loop. Adding visuals first would front-load licensing, asset-sourcing, and a whole visual-grounding sub-pipeline before we know the core loop retains anyone.
- **Reserving the slots makes visuals additive, not a migration.** Because the schema already has first-class visual blocks, turning them on later extends the grounding discipline rather than reshaping the data model.

**Trade-off:** V1 is less visually rich than the "highly visual" north star. Accepted — a proven text loop with reserved visual slots beats an unproven visual loop, and the slots mean we lose no future ground.

**Consequence:** when visuals arrive, they extend the existing grounding ledger (a visual ledger + an asset-sourcing stage) rather than introducing a parallel unverified path. The `diagram` block's concrete spec (chart types, node/edge schematics) is settled at that time, not now.
