---
name: distiller
description: the learning loop (out-of-band, batched)
---

- **Stage / fan-out:** not in the per-run pipeline; runs periodically over accumulated feedback.
- **Reads:** `feedback/verdicts.jsonl` + edit-diffs.
- **Produces:** a **proposed markdown diff** to DNA / guardrails / exemplars.
- **Honors:** [ADR 0004](../../docs/adr/0004-human-ratified-learning-loop.md) — the human **ratifies every diff**; nothing auto-merges.
- **Task:** batch-analyze verdicts → propose banned-phrase additions (from repeated deletions), new checks (from repeated reject reasons), exemplar promotions, DNA tweaks.
- **Done when:** a diff is proposed and **presented to the human**; only human-ratified diffs land.

---
