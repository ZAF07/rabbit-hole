# Leave & resume — Session boundary, resumable path, daily hook

Status: ready-for-agent
Feature: consumption-app
Blocked by: 02

## What to build

Let a reader's journey survive real life — a coffee, a meeting, a night's sleep — and pull them gently back ([ADR 0008](../../../docs/adr/0008-sessions-instrumented-from-v1.md), [ADR 0009](../../../docs/adr/0009-retention-earned-not-gamified.md)).

- **Session boundary (hybrid):** inactivity timeout (~30 min) **or** explicit app close, whichever comes first, ends the analytics Session. The **durable path outlives** the Session.
- `ResumeSession` restores the reader's **current Piece + backtrack stack**; resuming after a timeout gap starts a **new** Session that **continues the same path**.
- The **Daily Feature still greets** each day as the heartbeat, even when a resumable thread exists — always something fresh *and* a way back in.
- **One dignified daily notification** teasing the day's real hook (held to the same anti-clickbait bar as in-app hooks) — never a nag, never bait-and-switch. **No streaks / badges / points / leaderboards** — rejected outright.

## Acceptance criteria

- [ ] Inactivity ≥ ~30 min **or** app close ends the analytics Session.
- [ ] `ResumeSession` restores current Piece + backtrack stack after a close.
- [ ] Resuming after the gap begins a **new** Session that **continues the same** durable path.
- [ ] The Daily Feature is still served when a resumable thread exists.
- [ ] The daily notification teases the real hook; no gamification primitive exists anywhere in the surface.
- [ ] `ruff`, `mypy`, `pytest` pass.

## Blocked by

- consumption-app/issues/02 (the persisted path + backtrack stack to resume)
