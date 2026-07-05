# Sourcing Guardrails — source vetting & corroboration

Applied during Stage 2 (Researcher: **Vet** + **Corroborate** rounds). Governs which sources are credible and when a claim may enter the vetted claim pack. Operationalizes [ADR 0005](../../docs/adr/0005-closed-book-grounding.md).

## Source tiers
- **Primary / authoritative** — the study, official record, dataset, primary document, or the person directly involved.
- **Secondary** — reporting or analysis about a primary source.
- **Tertiary** — summaries of secondary material (encyclopedias, aggregators).

## Vet each source (Round 2b) — score on
- Authority (who; expertise; standing to know)
- Tier (primary / secondary / tertiary)
- Recency (and whether recency even matters for this claim)
- Bias / independence
- Corroboration (is it independently echoed?)
- Retractions / corrections history

Human-provided sources enter at a **trusted tier but are still checked**.

## Corroboration standard (Round 2c — the admission bar)
- A **primary / authoritative** source is **sufficient alone**.
- A **secondary / tertiary** claim needs **≥2 independent** credible sources. *Independent* = not citing each other, not the same origin; wire/echo repeats collapse to one. (Kills "everyone repeats the same myth.")
- **Internal-only, uncorroborated** claims are **dropped by default** — flagged to the human only if load-bearing for the premise (source it or cut).
- **Human-provided** sources count as primary (trusted tier) but still pass a basic reliability check.

The bar deliberately **protects** surprising single-primary-source facts while cutting unsourced and echo-chamber claims.

## The grounding ledger (per Piece, `pieces/<id>/grounding.json`)
- Per **claim**: text, tier, status (verified / dropped / flagged), corroborating sources, refutation verdict.
- Per **source**: citation, tier, credibility assessment (why it passed 2b), supporting excerpt, retrieval timestamp.

Persisted regardless of display, so any shipped fact is inspectable and a wrong fact is traceable to the exact source and round ([ADR 0005](../../docs/adr/0005-closed-book-grounding.md)).
