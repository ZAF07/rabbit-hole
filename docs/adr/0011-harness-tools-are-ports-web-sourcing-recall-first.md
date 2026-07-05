# The harness's tools are ports; V1 web sourcing is recall-first Playwright

[ADR 0010](0010-content-generation-pipeline-architecture.md) fixes the harness as a deterministic staged DAG — "not a free-roaming agent." That governs the *orchestration between stages*. **Within** a stage, an agent is a **tool-using LLM running a bounded loop** (the Researcher's Harvest→Vet→Corroborate→Refute; the Editor's machine-QA loop). This ADR records what external tools those loops may reach for, and how they are shaped: as **ports**, so the two messiest edges — a browser and a database — stay swappable and the domain stays clean (ports-and-adapters).

So the harness is **bounded agentic loops nested inside a deterministic staged DAG**. Tools live inside stages; the sequencing of stages stays fixed.

## Only two external tool seams

Every stage reads and writes files in the run workspace (`harness/runs/<id>/`); the deliverable-on-disk *is* the gate ([ADR 0010](0010-content-generation-pipeline-architecture.md)). Only two stages reach outside the workspace, each through one port:

| Port | Adapter (V1) | Used by | For |
| --- | --- | --- | --- |
| **`WebSourcePort`** | Playwright | Researcher (Stage 2) | fetching source content |
| **`ContentGraphRepository`** | Postgres | Architect (read) + publish step (write) | dedup at plan time; publishing approved content |

Writer, Editor, Weaver, and Reviewer use **no** external tools — pure file-in / file-out. The concentration is deliberate: fake these two ports and the whole pipeline runs offline and deterministically.

## `WebSourcePort` — fetch/navigate, never a search engine

- The V1 adapter is **Playwright** — it renders JS and returns a page's readable content, because many sources are not static HTML.
- It does **not** scrape Google or any search-results page — captchas and blockers make that brittle, and it isn't the job. The port exposes **`fetch(url)`** (returning readable content **plus the page's outbound links**) and a **bounded `follow`** (depth- and count-limited) — but **not** `search(query)`.
- **Discovery in V1 is recall-first, then citation-chasing.** The Researcher's own parametric recall proposes *candidate URLs* — exactly the role [ADR 0005](0005-closed-book-grounding.md) reserves for internal knowledge ("a recall aid… to decide where to look for sources"), **never as an authority**. But recall mostly surfaces **hub** pages (overviews, encyclopedia entries) — *tertiary* sources that can't clear the corroboration bar alone. So the port also **follows links off a fetched page** (bounded by depth and count) to reach the **primary sources those hubs cite** — the citation-chasing pattern: *recall a hub → harvest its references → fetch and vet those primaries.* This is how the harness reaches ≥2 independent **primary** sources it could never have named from memory, with no search engine. The Corroborate/Refute rounds vet everything against [`guardrails/sourcing.md`](../../harness/guardrails/sourcing.md).
- **The corroboration bar is unchanged.** Recall-first lowers *yield*, not the standard: a secondary/tertiary claim that cannot reach **≥2 independent** sources from recalled URLs is **cut, not shipped**. A **primary/authoritative** source still suffices alone, so surprising single-primary facts survive. The V1 corpus therefore skews toward strongly-anchored claims — a thinner but honest corpus, by design.
- Fetched content feeds the **grounding ledger** (supporting excerpt + retrieval timestamp, per [ADR 0005](0005-closed-book-grounding.md)) and is **snapshotted per run**, so a shipped fact is traceable to the exact bytes retrieved, re-runs need not re-hit the site, and we stay polite.
- **The SERP adapter is the planned swap-in.** When discovery breadth matters, a SERP/search service drops in behind the same port (adding `search(query)`), widening yield **without touching the corroboration bar or any domain code** — the whole reason this is a port.

## `ContentGraphRepository` — generation reads *and* writes it

The shorthand "generation writes, consumption reads" ([ADR 0006](0006-generation-and-consumption-are-separate.md)) is refined here: generation **reads** Content-Graph content (the Architect reads existing Pieces to bridge to them and avoid duplicates) **and writes** it (publishing approved content). What [ADR 0006](0006-generation-and-consumption-are-separate.md) forbids is unchanged — consumption never reads generation-only concepts, generation never depends on user/session data. Reading published Pieces to avoid duplicating them is squarely legitimate.

## Why
- **Ports keep the mess at the edge.** A browser runtime and a database are the two most adapter-shaped dependencies in the system; behind ports, the pipeline is testable with fakes and the V1→SERP path is a config swap, not a rewrite.
- **Recall-first is honest about V1.** It fits closed-book grounding rather than fighting it, and it fails loud (a thin pack yields a thin Piece that dies before drafting) rather than papering gaps with unverifiable recalled facts.

## Trade-off
Recall-first discovery — even with citation-chasing — yields a narrower source set than a search engine, and will still cut some genuinely-true claims it can't reach a second independent source for. Citation-chasing materially closes the gap (it reaches the primaries a hub cites, not just what the model can name); the SERP adapter is the deliberate, already-scoped remedy for what remains.

## Consequence
Governs the generation subsystem's **tool surface** only. The two ports are the sole external seams; new sourcing capability arrives as a new **adapter** behind `WebSourcePort`, not as new pipeline shape. What crosses the [ADR 0006](0006-generation-and-consumption-are-separate.md) boundary is still only Pieces, Connections, and Topics.
