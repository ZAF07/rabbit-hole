# Guided Intellectual Exploration

The domain model for a consumer intellectual-curiosity app: curated narrative content that users travel through by following connections between topics. This file is the glossary and nothing else — it defines the language, not the implementation.

## Two vocabulary layers

The internal (canonical) vocabulary is generic, obvious, and stable. The UI/UX vocabulary is an evocative "thread/weave" presentation layer mapped on top of it and may be rebranded freely. See [ADR 0001](docs/adr/0001-decouple-internal-and-ui-vocabulary.md).

**Rule:** code, data model, pipeline, and internal docs use the Internal term *only*. Branded UI strings live in exactly one place — the **presentation vocabulary module** (an i18n-style bundle keyed by internal term) — and are rendered from there. The app name itself is deliberately not yet chosen. See [ADR 0001](docs/adr/0001-decouple-internal-and-ui-vocabulary.md) for the mechanism.

| Internal (canonical) | UI/UX (branded) | Meaning |
| --- | --- | --- |
| **Piece** | Thread | One self-contained narrative on a single subject (~5 min). |
| **Connection** | Loose Thread / "Pull this thread" | A curated, directed link from one Piece to a related Piece, carrying its own hook copy. |
| **Topic** | Spool | A node in the content classification taxonomy; Pieces belong to many. |
| **Session** | an Unspool (verb: *unspooling*) | A user's continuous journey pulling Connections. |
| **Personal Knowledge Graph** | Tapestry | A User's own trail — the Pieces they've read + the Connections they pulled. Shown in V1; drives personalization in Phase 2. |
| **Daily Feature** | Today's Thread | The Piece promoted to the day's headline slot. |
| **Arc** *(V2)* | *(TBD)* | A bounded, finishable journey through a few Pieces toward a stated learning goal. |
| **Content Graph** | — | The corpus of Pieces joined by Connections. |
| **User** | — | A person with an account. |

## Language

**Piece**:
The atomic unit of curated content — one self-contained narrative on a single subject, paced for roughly a 5-minute read. Its body is an ordered list of **Content Blocks**, not freeform text. Audio narration and Deep Dive (longer explorations) are *renderings or variants* of a Piece, not separate kinds of thing.
_Avoid_: Article, post, lesson, card. (UI surface uses "Thread".)

**Content Block**:
One element of a Piece's body, drawn from a small fixed vocabulary — text blocks (`heading`, `paragraph`, `pull-quote`, `stat-callout`) and visual blocks (`image`, `gif`, `diagram`). A Piece's body is an ordered list of these. The fixed vocabulary is deliberate: each type is both a renderer commitment and a QA rule, which is what lets the generation harness assert a Piece's visual rhythm. Chosen over freeform markdown so "highly visual" is guaranteed by construction, not hoped for. See [experience.md](docs/experience.md).
_Avoid_: markdown, rich text, widget, component.

**Connection**:
A directed, editorially-authored link from one Piece to a related Piece. A Connection carries its own **hook** copy (the teaser that lures the user onward) — so the same destination Piece reached from two different origins can have two different hooks. The hook is where editorial taste lives; a Connection is never a bare graph edge. Connections are **independent of the Topic taxonomy** — a Connection freely joins Pieces in *different* Topics, and these cross-Topic Connections (the surprising jumps) are the product's most valuable content. See [ADR 0002](docs/adr/0002-taxonomy-and-content-graph-are-separate.md).
_Avoid_: Link, edge, branch, relation. (UI surface uses "Loose Thread".)

**Topic**:
A node in the content classification taxonomy — e.g. *Economics*, or the narrower *Behavioral Economics*. Topics self-nest: a Topic may have **one or more parent Topics** (a DAG, not a strict tree). A top-level Topic is informally a "category" and a nested one a "subcategory," but the canonical term for all of them is **Topic**. A Piece belongs to many Topics. Topics organize *content*; they never constrain Connections. Distinct from the Personal Knowledge Graph, which is per-*user*.
_Avoid_: category, subcategory, cluster, tag, domain — these describe a Topic's role or depth, not a separate concept. (UI surface uses "Spool".)

**Session**:
A user's continuous journey through the Content Graph, pulling one Connection after another — **linear, with backtracking** to try other forks. The ordered Pieces it visits form its *path*, which is **persisted** (the raw substrate for the Personal Knowledge Graph). Session **depth** = the number of *distinct* Pieces visited — the core engagement signal. A Session (the analytics window) is bounded by inactivity or app close; the durable path outlives it and is **resumable** across app opens. See [ADR 0008](docs/adr/0008-sessions-instrumented-from-v1.md).
_Avoid_: visit, run, trail. (UI surface uses "an Unspool".)

**Personal Knowledge Graph**:
A single per-user entity: the User's accumulated intellectual footprint — the subgraph of the Content Graph they have actually traversed (the Pieces they've read and the Connections they pulled), built from persisted Session paths ([ADR 0008](docs/adr/0008-sessions-instrumented-from-v1.md)). **One asset, two uses:** it is **shown** to the User as their own trail (a V1 feature and intrinsic retention driver — [ADR 0009](docs/adr/0009-retention-earned-not-gamified.md)), and it is **read to personalize** what gets surfaced (a **Phase 2** use of the same asset; Phase 2 may compute derived signals — Topic affinities, depth tolerance — but those are derivations of this one entity, never a separate one). Free in V1; a candidate premium feature later. A per-user artifact — distinct from the global Content Graph shared by all Users, and from the User (the identity).
_Avoid_: Interest Profile (the former name — it implied inference-only and was the source of a real modeling confusion), knowledge graph (bare — risks confusion with the Content Graph), preference graph, curiosity map, taste profile. (UI surface uses "Tapestry".)

**Arc** *(V2 — provisional)*:
A **bounded, curated, finishable** journey through a small set of Pieces toward a stated learning goal — *"5 Pieces to understand how modern maps work."* Unlike an open-ended Session, an Arc has a defined length and a **completion state**: a finishable intellectual object. The product's deliberate answer to infinite scroll — completion of understanding as the value, not endless content. A V2 concept; its authoring/curation model is undesigned. See [ADR 0009](docs/adr/0009-retention-earned-not-gamified.md).
_Avoid_: course, curriculum, module, lesson (the product is lighter than a course), playlist.

**Daily Feature**:
The single Piece promoted into the day's headline slot — the app's front door on any given day. A curation/scheduling role assigned to a Piece, not a distinct kind of content. The *current* Daily Feature on a given day is the most recently assigned one **on or before** that day — a day with no assignment inherits the previous one rather than leaving the front door empty, and a future-dated assignment is never surfaced early.
_Avoid_: daily pick, featured article, home card. (UI surface uses "Today's Thread".)

**Content Graph**:
The entire corpus modelled as Pieces (nodes) joined by Connections (edges). This is the graph users *traverse*, and it is separate from the Topic taxonomy that *classifies* Pieces (see [ADR 0002](docs/adr/0002-taxonomy-and-content-graph-are-separate.md)). Deliberately *not* a formal knowledge graph or ontology — it is a curated, editorial structure.
_Avoid_: knowledge graph, ontology, concept map.

**User**:
A person with an account. Kept strictly distinct from their Personal Knowledge Graph — the User is the identity; the Personal Knowledge Graph is their accumulated intellectual trail.
_Avoid_: reader, member, account, learner.
