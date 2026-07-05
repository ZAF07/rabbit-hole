---
name: editor
description: the anti-slop pass + machine-QA loop
---

- **Stage / fan-out:** 4 · Edit — per Piece.
- **Reads:** `draft.md`, DNA, the Voice Profile, [`guardrails/piece.md`](../guardrails/piece.md).
- **Produces:** `pieces/<id>/piece.md` — the final Piece.
- **Honors:** piece.md, DNA, Voice Profile.
- **Task:** tone/pacing/anti-slop edit; then the **machine-QA judge** applies piece.md and **loops the edit** until pass or QA budget spent; then **4.5 grounding check** — every assertion maps to a verified claim, drift/embellishment cut or re-sourced.
- **Done when:** `piece.md` passes **all** piece.md checks *and* the grounding check; otherwise flagged/escalated, never silently shipped.
