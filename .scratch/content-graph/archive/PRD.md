# PRD: The Content Graph — shared store & repository port

Status: completed
Feature: content-graph
Depends on: — (foundational; `generation-harness` and `consumption-app` both depend on this)

> The Content Graph is the **one and only** artifact the two subsystems share ([ADR 0006](../../docs/adr/0006-generation-and-consumption-are-separate.md)). This PRD builds it first because both other tracks import its port and schema.

## Problem Statement

Rabbit Hole is two independent subsystems — a generation **harness** that *writes* content and a consumption **app** that *reads* it — that must share nothing except the corpus itself ([ADR 0006](../../docs/adr/0006-generation-and-consumption-are-separate.md)). Today there is no store and no agreed shape for a Piece. If each subsystem invents its own model of a Piece, a Connection, or a Topic, three things break at once:

1. **The boundary blurs.** Generation-only concepts (run id, constellation, grounding ledger, theme brief) leak into the reader, or the app starts reasoning about "which batch made this" — a fusion that is expensive to unwind once queries depend on it.
2. **Graph integrity is unenforceable.** Nothing guarantees a Connection resolves to a real Piece, that Topics can carry more than one parent, or that a Piece's body is an ordered, typed sequence rather than a blob.
3. **Nothing can be built on top.** Neither the pipeline nor the reader can be written or tested until there is a settled contract to write to and read from.

The team needs a durable, Postgres-backed Content Graph with a settled schema and a single access port — the physical seam between the two worlds.

## Solution

A **Postgres**-backed Content Graph exposed through one **`ContentGraphRepository`** port (ports-and-adapters). The port *is* the Content Graph boundary: generation calls its write methods (and reads the graph at plan time to avoid duplicating existing Pieces — [ADR 0011](../../docs/adr/0011-harness-tools-are-ports-web-sourcing-recall-first.md)), consumption calls only its read methods, and neither subsystem imports anything else of the other's ([ADR 0006](../../docs/adr/0006-generation-and-consumption-are-separate.md)). The relational schema models the three durable, consumption-facing entities and nothing generation-only:

- **Topics** as a shallow **multi-parent DAG** — a Topic may have more than one parent; a Piece belongs to many Topics ([ADR 0002](../../docs/adr/0002-taxonomy-and-content-graph-are-separate.md)).
- **Pieces** whose `body` is an **ordered list of typed Content Blocks** (a fixed vocabulary), plus `title`, `teaser`, `readTimeMin`, `topics[]`.
- **Connections** as **directed edges** carrying their **own per-origin `hook`** — never a bare edge; the same destination reached from two origins can pitch two different hooks.

Because the store sits behind the port, **Docker (local) ↔ Supabase (scale) is a connection-config swap, not a code change**. The feature ships with an **in-memory fake** implementing the same port and a **shared contract-test suite** run against *both* the fake and the real Postgres adapter — so the fake other tracks build on stays honest and the SQL is proven.

## User Stories

*Actors: the **generation harness** (write-client), the **consumption app** (read-client), the **developer** building on the store, the **operator** running it.*

1. As the generation harness, I want to write a finished Piece — its title, teaser, read-time, Topic tags, and ordered Content Blocks — into the store in one operation, so that a completed run becomes durable content.
2. As the generation harness, I want to write a directed Connection with its per-origin hook between two existing Pieces, so that the traversable graph is populated.
3. As the generation harness, I want the store to reject a Connection whose destination Piece does not exist, so that dead links (violating invariant I5) can never be persisted.
4. As the generation harness, I want to upsert Topics and attach zero or more parent Topics to each, so that the multi-parent DAG taxonomy ([ADR 0002](../../docs/adr/0002-taxonomy-and-content-graph-are-separate.md)) is faithfully stored.
5. As the generation harness, I want to tag a Piece with many Topics, so that classification reflects that a Piece legitimately belongs to several.
6. As the generation harness, I want a Piece's Content Blocks stored **in order** with their type preserved, so that the reader can reproduce the exact authored visual rhythm.
7. As the generation harness, I want writes to be idempotent by Piece/Connection/Topic identity, so that re-running or resuming a run does not create duplicates.
8. As the consumption app, I want to fetch the current **Daily Feature** Piece, so that I can render the app's front door.
9. As the consumption app, I want to fetch a single Piece by id with its full ordered body, so that I can render the reading view.
10. As the consumption app, I want to fetch the **outbound Connections** of a Piece — each with its hook and the destination's title and Topics — so that I can render "pull this thread" preview cards without a second round-trip per card.
11. As the consumption app, I want to resolve a Connection's destination id to a real Piece, so that pulling a thread always lands on real content.
12. As the consumption app, I want to read a Piece's `teaser` for entry-point surfaces and its Connections' `hook` copy for onward surfaces, so that the two distinct lures are never conflated.
13. As the consumption app, I want the read models I receive to contain **no** generation-only fields (run id, constellation, grounding ledger), so that the boundary cannot leak into the experience ([ADR 0006](../../docs/adr/0006-generation-and-consumption-are-separate.md)).
14. As the consumption app, I want to look up Topics (with parents) for a set of Pieces, so that the Tapestry can color and cluster nodes by Topic.
15. As a developer, I want a single `ContentGraphRepository` port with a clear read surface and write surface, so that I depend on an interface, not on Postgres.
16. As a developer, I want an in-memory fake that satisfies the same port, so that domain and application tests run fast with no database.
17. As a developer, I want one contract-test suite that runs against both the fake and the Postgres adapter, so that the two implementations can never silently diverge.
18. As a developer, I want the schema reserved for `image`/`gif`/`diagram` block kinds even though V1 never populates them, so that adding visuals later is a data change, not a migration of every Piece ([ADR 0007](../../docs/adr/0007-visual-provenance-sourced-or-data-grounded.md)).
19. As a developer, I want only internal (canonical) vocabulary in the schema and port — Piece, Connection, Topic, never "Thread"/"Spool" — so that branded strings stay in the presentation layer alone ([ADR 0001](../../docs/adr/0001-decouple-internal-and-ui-vocabulary.md)).
20. As an operator, I want the store selected by connection config, so that pointing local dev at Docker and production at Supabase requires no code change.
21. As an operator, I want schema changes expressed as versioned, forward migrations, so that the store can evolve safely.
22. As an operator, I want referential integrity enforced in the database (Connections → Pieces, block → Piece, piece_topic → both), so that corruption is impossible even if application code has a bug.
23. As a curator, I want the current Daily Feature to be an assignable role (a date-keyed pointer to a Piece), so that the front door can change day to day without touching Piece content.
24. As a developer, I want to query a Piece's inbound and outbound Connections, so that constellation-level checks (dead-ends, connectedness) and the Tapestry can be computed.
25. As the generation harness, I want a `run_id` storable on a Piece purely for debug provenance, so that a shipped error is traceable upstream — while consumption never keys off it ([ADR 0006](../../docs/adr/0006-generation-and-consumption-are-separate.md)).

## Implementation Decisions

**Modules built**
- A `content_graph` **domain** package — the entities `Piece`, `ContentBlock`, `Connection`, `Topic` as plain, framework-free types. Internal vocabulary only.
- The **`ContentGraphRepository` port** — one interface with a read surface and a write surface (see below). Per the chosen design, it is a **single shared port**; the discipline of [ADR 0006](../../docs/adr/0006-generation-and-consumption-are-separate.md) — **consumption never writes; generation may read (dedup) and write (publish)** — is enforced by **convention and review**, not the type system. (The wiring keeps it honest: the consumption app composes only the read methods into its use-cases; the harness composes the write methods plus read-for-dedup.)
- A **Postgres adapter** implementing the port.
- An **in-memory fake** implementing the port — the fast test substrate the other two tracks import.
- A **migration** mechanism producing the schema.

**Schema (relational, internal vocabulary)**
- `topics` — `id`, `slug`, `title`. Self-nesting via a `topic_parents(child_id, parent_id)` join table so a Topic can have **zero or more** parents (the DAG; a strict single-parent tree is explicitly rejected — [ADR 0002](../../docs/adr/0002-taxonomy-and-content-graph-are-separate.md)).
- `pieces` — `id`, `title`, `teaser`, `read_time_min`, timestamps, nullable `run_id` (debug provenance only, never in a consumption read model).
- `piece_topics(piece_id, topic_id)` — many-to-many; a Piece belongs to many Topics.
- `blocks` — `id`, `piece_id`, `ordinal`, `kind`, `payload` (JSONB). `kind ∈ {heading, paragraph, pull-quote, stat-callout, image, gif, diagram}`. Ordering is by `ordinal`. `payload` shape is per-kind (e.g. `paragraph→{text}`, `stat-callout→{value,label}`, `pull-quote→{text, attribution?}`). **V1 validates and populates the four text kinds only**; visual kinds are reserved but never written ([ADR 0007](../../docs/adr/0007-visual-provenance-sourced-or-data-grounded.md)).
- `connections` — `id`, `from_piece_id`, `to_piece_id`, `hook`. Directed. `hook` (the per-origin lure) lives **on the edge**, not the destination. FK on both endpoints; `(from_piece_id, to_piece_id)` unique.
- `daily_features` — `date`, `piece_id`. The Daily Feature is a scheduling role, not a kind of Piece.

**Port interface (single `ContentGraphRepository`)**
- *Read surface (consumption uses this):* `get_daily_feature()`, `get_piece(id)` (with ordered body), `get_connections_from(piece_id)` (each returning hook + destination title + destination topics for preview cards), `get_topics_for(piece_ids)`, `get_piece_summaries(piece_ids)`.
- *Write surface (generation uses this):* `upsert_topic(...)`, `set_topic_parents(...)`, `upsert_piece(piece_with_ordered_blocks_and_topics)`, `upsert_connection(from, to, hook)`, `set_daily_feature(date, piece_id)`.
- Read methods return **read models that exclude** `run_id` and any generation-only field.

**Cross-cutting**
- Referential integrity (I5's persistence-level backstop) is enforced by FK constraints; the schema *supports* computing dead-ends (I4), cross-Topic Connections (I6), and connectedness (I7) but does **not** itself guarantee them — those are generation-time invariants owned by `generation-harness`.
- Store selection (Docker vs Supabase) is read from config (`config.py` / `.env`), never hardcoded.
- No secrets in code.

## Testing Decisions

**What a good test is here:** it exercises the store through the **port's public methods** and asserts observable behavior (what round-trips, what resolves, what is rejected) — never SQL internals or table layout, which are free to change.

- **The one seam: a shared contract-test suite** parametrized over `[in-memory fake, Postgres adapter]`. Every behavioral test runs against both, proving they agree. Covers:
  - Round-trip a Piece with ordered mixed text blocks → read back identical order and types.
  - A Piece with several Topics; a Topic with several parents → the DAG survives.
  - Write a Connection → `get_connections_from` returns it with hook + joined destination title/Topics.
  - Reject a Connection whose destination Piece is absent.
  - Read models omit `run_id` / generation-only fields.
  - `set_daily_feature` then `get_daily_feature` returns the pointed-to Piece.
  - Upserts are idempotent by identity (no duplicate on re-write).
- **Postgres adapter integration** runs the same suite against **Postgres in Docker** (a docker-compose service / testcontainer), so migrations and SQL are verified, not just the fake.
- **Prior art:** none — this establishes the contract-test-against-both pattern that `consumption-app` reuses for its user/session tables.

## Out of Scope

- **Populating visual blocks** (`image`/`gif`/`diagram`) — slots are reserved in the schema; nothing writes them in V1 ([ADR 0007](../../docs/adr/0007-visual-provenance-sourced-or-data-grounded.md)).
- **User / Session / Tapestry storage** — those tables belong to `consumption-app`; the Content Graph is what the Tapestry *references*, not where it lives.
- **The generation pipeline and the reader API** — separate PRDs.
- **Enforcing constellation invariants** (dead-ends, coverage, cross-Topic) — a generation-time responsibility; the schema only *enables* checking them.
- **Auth / accounts, presentation vocabulary bundle, any branded strings.**

## Further Notes

- This single port is the literal seam of [ADR 0006](../../docs/adr/0006-generation-and-consumption-are-separate.md). The team accepted (in PRD scoping) that a single shared port keeps the read/write split a **convention** rather than a compiler-enforced wall; the mitigation is that each subsystem's composition wires only its own half, and code review guards the rule. If the convention ever proves leaky, splitting into `ContentGraphReader` + `ContentGraphWriter` over the same schema is a non-breaking refactor.
- Internal ↔ branded vocabulary map is authoritative in [CONTEXT.md](../../CONTEXT.md); nothing here imports branded strings ([ADR 0001](../../docs/adr/0001-decouple-internal-and-ui-vocabulary.md)).
- Seed Topics for first content come from [taxonomy.md](../../docs/taxonomy.md) (the "systems of the modern world" V1 cluster); loading them is a small write-path task.

## Completion

- Completed: 2026-07-05
- Commit: <to be filled in manually>
