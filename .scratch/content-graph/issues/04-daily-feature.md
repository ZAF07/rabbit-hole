# The Daily Feature — a date-keyed pointer to a Piece

Status: ready-for-agent
Feature: content-graph
Blocked by: 01

## What to build

The app's front door as an **assignable scheduling role**, not a kind of Piece: a date-keyed pointer that names which existing Piece is the Daily Feature, so the front door can change day to day without touching Piece content.

- Migration adds `daily_features(date, piece_id)`.
- Port methods: `set_daily_feature(date, piece_id)` and `get_daily_feature()` (returns the currently-pointed-to Piece).

## Acceptance criteria

- [ ] `set_daily_feature(date, piece)` then `get_daily_feature()` returns the pointed-to Piece.
- [ ] Re-assigning the Daily Feature for a date replaces the pointer (no duplicate rows).
- [ ] `get_daily_feature` returns a Piece read model with no generation-only fields.
- [ ] Behaviors pass against **both** fake and Postgres-in-Docker.
- [ ] `ruff`, `mypy`, `pytest` pass.

## Blocked by

- content-graph/issues/01 (port, Piece, adapters, contract-test harness)
