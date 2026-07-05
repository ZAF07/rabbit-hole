# Walking skeleton — Daily Feature → Read Piece → connection previews

Status: ready-for-agent
Feature: consumption-app
Blocked by: content-graph/issues/01-04

## What to build

The reader backend's walking skeleton: a reader can land on the Daily Feature, read a Piece rendered from its ordered Content Blocks, and see where it Connects — all driven through the **application-service boundary** over an in-memory `ContentGraphRepository` fake seeded with a fixture constellation.

- The uv project and a `consumption` domain / application-service package — framework-free, **internal vocabulary only**. First use-cases: `GetDailyFeature` and `ReadPiece`.
- `GetDailyFeature` returns the editorially-chosen entry Piece (same for everyone in V1) with its **`teaser`**.
- `ReadPiece` returns ordered **Content Blocks** (text kinds only — [ADR 0007](../../../docs/adr/0007-visual-provenance-sourced-or-data-grounded.md)) + **connection previews**, each preview joining `toPieceId` → destination `title` + `topics` and showing the Connection's **`hook`**. Entry uses the Piece's teaser; onward jumps use the Connection's hook — the two lures are never conflated.
- The **presentation vocabulary module** — the app's only source of branded strings, an i18n-style bundle keyed by internal term (`vocab.piece.one → "Thread"`, `vocab.interestProfile → "Tapestry"`, …). The UI renders from it; the **domain and API never import it** ([ADR 0001](../../../docs/adr/0001-decouple-internal-and-ui-vocabulary.md)).
- Boundary guard: the reader reads **only** Pieces and Connections; read models expose **no** `run_id` / constellation ([ADR 0006](../../../docs/adr/0006-generation-and-consumption-are-separate.md)).

## Acceptance criteria

- [ ] `GetDailyFeature` returns an entry-worthy Piece **with its `teaser`**.
- [ ] `ReadPiece` returns ordered Content Blocks + connection previews, each with `hook` + joined destination `title`/`topics`.
- [ ] Optionally peeking at a Piece's onward Connections up front (Topics + hooks) works before reading begins.
- [ ] Branded strings render **only** from the presentation vocabulary module; a test asserts the domain/API layer imports no branded string.
- [ ] A boundary test asserts the reader never depends on a generation-only field (`run_id`, constellation).
- [ ] The loop is exercised through the app-service interface over the in-memory ContentGraph fake + fixture constellation.
- [ ] `ruff`, `mypy`, `pytest` pass.

## Blocked by

- content-graph/issues/01-04 (read surface: Pieces + blocks, Topics, Connections/previews, Daily Feature — and the in-memory fake to seed a fixture constellation)
