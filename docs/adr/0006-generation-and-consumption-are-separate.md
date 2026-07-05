# Generation and consumption are separate worlds joined only by the Content Graph

The system has two **independent** subsystems that share no concepts except the Content Graph:

- **Generation** — the agentic run/loop. A *mechanism* that collects and generates Pieces, Connections, hooks, and Topic tags (batched per run as a *constellation*) and writes them into the Content Graph. It knows nothing about users, Sessions, or the app.
- **Consumption** — the app. Reads **only Pieces and Connections** from the Content Graph. It knows nothing about runs, constellations, theme briefs, grounding rounds, or how content was made.

The **Content Graph is the sole boundary** — the only shared artifact. Generation writes to it; consumption reads from it. A run is upstream plumbing; a Session is downstream experience; neither references the other's vocabulary.

**Why:**
- **Hard to reverse** — if consumption ever reads "which run/constellation produced this Piece" to shape the experience, the two worlds fuse, and you can never change, swap, or regenerate the generation mechanism without touching the app.
- **Surprising** — a "run" or "constellation" *sounds* like it might be a user-facing bundle ("today's fresh batch"). It is strictly not. This ADR exists to stop that leak.
- **Real trade-off** — coupling them (a Session scoped to a constellation, the app surfacing generation batches) is tempting and simpler short-term, but it fences the journey and welds the app to the factory.

**Consequence:** the durable, consumption-facing entities are **Pieces, Connections, Topics**. Generation-only concepts (constellation, run id, theme brief, grounding ledger) live entirely upstream of the Content Graph and never appear in consumption code or UX. A run id may be stored on a Piece for debugging provenance, but consumption never keys off it.
