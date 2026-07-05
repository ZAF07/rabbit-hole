# Identity + linear Session path — pull a thread, backtrack, depth

Status: completed
Feature: consumption-app
Blocked by: 01

## What to build

Give the reader an identity and a persisted journey: a single advancing thread with a backtrack stack (not free-roam), the raw substrate the Tapestry will later render ([ADR 0008](../../../docs/adr/0008-sessions-instrumented-from-v1.md)).

- **Ports + in-memory fakes:** a `UserRepository` / identity port and a `SessionRepository` (durable path + backtrack stack).
- Use-cases: `PullConnection` advances the path to the destination Piece and **appends** it; `Backtrack` pops the stack to the prior Piece (return the way you came, stack semantics) and permits pulling a **different** outbound Connection from there.
- **No arbitrary free-roam jumps** across the whole graph in V1 — the experience is a guided journey, not a search box.
- **Session depth = distinct Pieces visited** (deduped): re-reading a seen Piece does **not** increase depth; popping back to pull a new fork does.
- The path is **persisted** from V1 even though nothing personalizes yet — recording ≠ personalizing.

## Acceptance criteria

- [x] `PullConnection` advances to the destination and appends it to the path.
- [x] `Backtrack` pops to the prior Piece and then permits pulling a **different** Connection from it (alternative branch).
- [x] Backtracking behaves like a **stack** (returns the way it came), not a teleport.
- [x] **Depth counts distinct Pieces** — re-reading a seen Piece does not increase it; pulling a new fork does.
- [x] There is no API for arbitrary free-roam jumps.
- [x] The path is persisted per user via the (fake) session/user repos.
- [x] `ruff`, `mypy`, `pytest` pass.

## Blocked by

- consumption-app/issues/01 (the read use-cases + app-service boundary the journey advances over)

## Completion

- Completed: 2026-07-05
- Commit: `46cfb47c60352c4929377ca5f4e395c1ffdfd869`
