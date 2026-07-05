# Source stage real — the Researcher + WebSourcePort (recall-first, citation-chasing)

Status: completed
Feature: generation-harness
Blocked by: 03

## What to build

Replace the stubbed source stage with the real **closed-book Researcher** and the **`WebSourcePort`** it uses. Per planned Piece, run the adversarial sub-pipeline and produce the vetted claim pack + grounding ledger the Writer will draft from.

- **`WebSourcePort`** — a Playwright adapter that `fetch(url) → content + outlinks` (renders JS) and performs **bounded citation-chasing** (`follow` cited links to a bounded depth/count), **not** a Google-search scraper. V1 discovery is **recall-first**: the model recalls candidate URLs (mostly hub/tertiary pages), Playwright fetches them, then follows the links those hubs **cite** to reach the **primary sources** ([ADR 0011](../../../docs/adr/0011-harness-tools-are-ports-web-sourcing-recall-first.md)). A SERP adapter is swappable in later behind the same port; no search engine in V1.
- The **2a Harvest → 2b Vet → 2c Corroborate → 2d Refute** sub-pipeline. Corroboration bar (from `sourcing.md`): a **primary source suffices alone**; secondary/tertiary needs **≥2 independent** sources; internal-only uncorroborated claims are **dropped by default** (flagged to the human only if load-bearing).
- Per-Piece **grounding ledger** persisted (claim → tier → status → sources → refutation verdict); fetched content snapshotted per run.
- A **thin source pack fails loud and early — before the Writer runs** — never papered over in prose.

Tested entirely through a **faked `WebSourcePort`** (canned page content + outlinks keyed by URL) so tests stay deterministic and offline.

## Acceptance criteria

- [x] The Researcher reaches a **primary source by following a recalled hub's cited link** (via the faked port), not by any search-query call — there is no `search(query)` in the port surface.
- [x] A claim whose second independent source **can't be reached** from recalled/chased URLs is **cut, not shipped**; a single-**primary**-source claim survives.
- [x] An internal-only uncorroborated claim is **dropped/flagged**, never silently kept.
- [x] A **thin source pack fails before** the Draft stage runs.
- [x] The grounding ledger records claim → tier → status → sources → refutation verdict, completely.
- [x] `ruff`, `mypy`, `pytest` pass.

## Blocked by

- generation-harness/issues/03 (the Architect's `plan.md` — the Piece concepts to research)

## Completion

- Completed: 2026-07-05
- Commit: `7af81e040b8b2425c330f3f874ccc206be43fe85`
