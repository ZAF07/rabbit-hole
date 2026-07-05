# The Daily Feature — a date-keyed pointer to a Piece

Status: completed
Feature: content-graph
Blocked by: 01

## What to build

The app's front door as an **assignable scheduling role**, not a kind of Piece: a date-keyed pointer that names which existing Piece is the Daily Feature, so the front door can change day to day without touching Piece content.

- Migration adds `daily_features(date, piece_id)`.
- Port methods: `set_daily_feature(date, piece_id)` and `get_daily_feature()` (returns the currently-pointed-to Piece).

## Acceptance criteria

- [x] `set_daily_feature(date, piece)` then `get_daily_feature()` returns the pointed-to Piece.
- [x] Re-assigning the Daily Feature for a date replaces the pointer (no duplicate rows).
- [x] `get_daily_feature` returns a Piece read model with no generation-only fields.
- [x] Behaviors pass against **both** fake and Postgres-in-Docker.
- [x] `ruff`, `mypy`, `pytest` pass.

## Blocked by

- content-graph/issues/01 (port, Piece, adapters, contract-test harness)

## Completion

- Completed: 2026-07-05
- Commit: `9a1f8e57077a577cf522916f54cd3ddd6138054a`
