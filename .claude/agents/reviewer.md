---
name: reviewer
description: Constellation QA
tools: Bash
---

- **Stage / fan-out:** 6 · Constellation QA — runs once.
- **Reads:** the whole constellation, [`guardrails/constellation.md`](../guardrails/constellation.md).
- **Produces:** `qa.md` — Tier-1 invariant results + Tier-2 coherence verdict.
- **Tools:** `Bash`, scoped to the `harness check-constellation` CLI (asserts the Tier-1 invariants I1–I8 — [ADR 0019](../../docs/adr/0019-claude-code-generation-runtime-and-shared-harness-cli.md)).
- **Honors:** constellation.md.
- **Task:** assert **Tier-1 invariants (I1–I8), binary**; judge **Tier-2 coherence (J1–J5)**; loop or flag.
- **Done when:** all Tier-1 invariants pass; Tier-2 flags resolved or escalated to the human queue. (Surviving Pieces then enter the human review gate — [ADR 0004](../../docs/adr/0004-human-ratified-learning-loop.md).)
