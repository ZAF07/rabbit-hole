# Theme Brief — the run's `goal.md`

A **Theme Brief** is the single human input that seeds one generation run. One Brief → one **constellation** (~30 Pieces spanning 4–5 Topics, wired by cross-Topic Connections). It is the run's `goal.md`, lives in `harness/runs/<id>/goal.md`, is **ephemeral generation input** (never a stored domain entity, never crosses to consumption — [ADR 0006](../../docs/adr/0006-generation-and-consumption-are-separate.md)), and is what **Stage 0 gates on**: a Brief with any unfilled `<placeholder>` fails the gate.

## The deal — a *medium* brief: you direct, the Architect designs, you approve

You are the **editor, never the writer** ([ADR 0004](../../docs/adr/0004-human-ratified-learning-loop.md)). So the Brief carries **direction + anchors**, not a hand-drawn constellation:

- You set the **through-line**, the **target Topics**, and the **Piece count** (required), and may drop in **anchors** — seed sources, must-includes, entry hints, must-avoids (optional).
- The **Architect** ([where the moat lives](../../docs/adr/0010-content-generation-pipeline-architecture.md)) invents every Piece concept and the whole Connection skeleton *around* your anchors, so the structural guarantees hold by construction ([ADR 0003](../../docs/adr/0003-plan-first-generation.md)).
- You get the detailed edit at the **plan-approval gate** — approve, edit, or reject the Architect's `plan.md` before any Piece is written.

So control sits in **two** places: creative direction here, detailed design at the gate. You never have to design 30 Pieces by hand, but nothing surprising ships without your yes.

## How to use

1. Copy the fenced block below into `harness/runs/<id>/goal.md`.
2. **Fill every `<placeholder>`** in the REQUIRED block; **keep or delete** each OPTIONAL field.
3. Leave no `<...>` behind — Stage 0 rejects placeholders.

---

## The template

```markdown
---
# ── REQUIRED ────────────────────────────────────────────────
through_line: >
  <one or two sentences: the editorial spine that makes these ~30 Pieces
   feel like ONE themed set, not a topic dump. This is the run's "why".>

target_topics:            # 4–5 Topics from docs/taxonomy.md the run must span (feeds I3)
  - <Topic>
  - <Topic>
  - <Topic>
  - <Topic>

piece_count: 30           # target count (feeds I1); a range like 28–32 is fine

# ── OPTIONAL — delete any block you don't use ───────────────
seed_sources:             # human-curated refs; enter at TRUSTED tier but still vetted (ADR 0005/0011)
  - <url or citation>

must_include:             # specific angles/Pieces the Architect MUST place in the plan
  - <angle>

entry_hints:              # angles that should open COLD as a Daily Feature (feeds J3)
  - <angle>

must_avoid:               # framings / sub-topics to steer clear of
  - <angle>

voice: narrative-nonfiction   # optional per-run Voice Profile; omit to use the active default
---

## Notes to the Architect  *(optional free prose)*
<anything that doesn't fit a field — a tone nuance, a personal angle, why this theme now.>
```

---

## A worked example (filled)

```markdown
---
# ── REQUIRED ────────────────────────────────────────────────
through_line: >
  The invisible systems that move the physical world — and how a single failure
  in one (a blocked strait, a fab going dark) cascades into all the others.

target_topics:                 # one from each V1 category — maximizes cross-Topic jumps
  - Logistics & Supply Chains   # Engineering & Infrastructure
  - Semiconductors              # Technology & Computing
  - Financial Systems           # Economics & Markets
  - Chokepoints & Geography     # Geopolitics & Power
  - Military Logistics          # Warfare & Strategy

piece_count: 30

# ── OPTIONAL ────────────────────────────────────────────────
seed_sources:
  - Levinson, *The Box* (2006) — container standardization & intermodal shipping
  - US EIA — world oil transit chokepoints briefing

must_include:
  - The shipping-container story as a spine Piece — it touches all five Topics.
  - How a $3 t-shirt encodes the whole supply chain.

entry_hints:
  - The container Piece and the "$3 t-shirt" Piece should each open cold as a Daily Feature.

must_avoid:
  - Day-to-day market / price commentary. Keep it structural, not news-cycley.
---

## Notes to the Architect
Lead with the physical and concrete (a ship, a port, a chip), then reveal the
system behind it. The reader should finish feeling the world is quietly wired
together — the whole point is the cross-Topic "everything connects" jolt.
```

---

## Field reference

| Field | Req? | Feeds | Notes |
| --- | --- | --- | --- |
| `through_line` | ✅ | J5 (coherent theme) | The spine. Vague theme → scattered constellation. |
| `target_topics` | ✅ | I3 (Topic coverage) | 4–5 **canonical** Topics from [taxonomy.md](../../docs/taxonomy.md). Spanning categories maximizes cross-Topic Connections (I6). |
| `piece_count` | ✅ | I1 (count) | Number or small range; ~30 is the default constellation size. |
| `seed_sources` | — | grounding | Enter at trusted (primary) tier but are still vetted ([ADR 0005](../../docs/adr/0005-closed-book-grounding.md)/[0011](../../docs/adr/0011-harness-tools-are-ports-web-sourcing-recall-first.md)). URLs or citations. |
| `must_include` | — | Architect plan | Angles the Architect must place. Your guaranteed intent. |
| `entry_hints` | — | J3 (entry-worthy nodes) | Which angles should stand alone as a Daily Feature. |
| `must_avoid` | — | Architect plan | Framings to keep out. |
| `voice` | — | Writer/Editor | Per-run [Voice Profile](../editorial/voices/) override; omit for the active default (`narrative-nonfiction`). |
| Notes to the Architect | — | Architect plan | Free prose for nuance that doesn't fit a field. |

The Brief is a **living template** — like the DNA and guardrails, it's markdown you tune over time, not code.
