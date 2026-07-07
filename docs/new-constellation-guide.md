# Running `/new-constellation` — the Claude Code generation runtime

This is the operator guide for driving **one full content-generation run with
Claude Code as the runtime** ([ADR 0019](adr/0019-claude-code-generation-runtime-and-shared-harness-cli.md)).
Claude Code is a *second real engine* alongside production DeepSeek/LangGraph:
it walks the same `harness/manifest.toml`, honors the same specs, and is forced
through the same `harness` CLI seam (`fetch` / `check-*` / `verdict` / `publish`)
and the same atomic write. **Claude does the creative and judgment work; the
shared CLI enforces the binary contract and does the write.** DeepSeek is never
called on this path.

For the *other* runtime — the in-process DeepSeek engine you drive with
`harness run` — see [running-a-generation-run.md](running-a-generation-run.md).
Everything below is specific to the Claude runtime.

> **The one thing that trips people up:** the run's input file, `goal.md`, is a
> **structured Theme Brief** (front-matter), *not* a sentence. Its
> `target_topics` must be the **exact slugs of Topics already seeded in your
> Postgres** — a wrong slug fails loud at the write (`TopicNotFoundError`) and
> nothing is persisted. You author `goal.md` by hand before invoking the skill;
> the conductor never invents topics for you.

---

## 1. What must be added and started (preconditions)

All of these are the same infra the production engine needs, plus the runtime
stamp. Do them once per machine/session.

| # | What | Command | Why |
| - | ---- | ------- | --- |
| 1 | **Docker Postgres up** | `docker compose up -d postgres` | the Content Graph (listens on `localhost:5433`) |
| 2 | **`.env` configured** | see below | DB URL + generation keys |
| 3 | **Extras installed** | `uv sync --extra llm --extra web` | the LLM adapter + Playwright web port |
| 4 | **Playwright browser** | `uv run playwright install chromium` | `harness fetch` drives a real headless browser |
| 5 | **Topic taxonomy seeded** | one-liner in [USAGE.md](../USAGE.md) §4 | the Topics your brief will target must exist |
| 6 | **Stamp the runtime** | `export HARNESS_RUNTIME=claude-code` and `export HARNESS_MODEL=claude-opus-4-8` | so verdicts are attributed to Claude, not DeepSeek ([ADR 0019](adr/0019-claude-code-generation-runtime-and-shared-harness-cli.md) §6) |

`.env` must contain at least:

```
DATABASE_URL=postgresql://rabbit:rabbit@localhost:5433/rabbithole
LLM_PROVIDER=deepseek
LLM_API_KEY=<your key>
LLM_MODEL_PRECISE=<precise model id>
LLM_MODEL_CREATIVE=<creative model id>
```

> The LLM keys are still required even though DeepSeek does not author on this
> path: the CLI's composition root wires the production adapter unconditionally.
> The subagents author; the LLM env just has to be present and valid.

### Preflight (copy-paste)

Run this before invoking the skill. It confirms the DB is up, the taxonomy is
seeded, and the runtime is stamped — failing loud rather than mid-run.

```bash
# Postgres reachable + taxonomy seeded (prints the count; expect 29)
uv run python -c "import os, psycopg; from dotenv import load_dotenv; load_dotenv(); \
c=psycopg.connect(os.environ['DATABASE_URL']); \
print('topics seeded:', c.execute('select count(*) from topics').fetchone()[0])"

# Runtime stamped for this shell (must print claude-code / your model)
echo "runtime=$HARNESS_RUNTIME model=$HARNESS_MODEL"

# CLI is wired
uv run harness --help >/dev/null && echo "harness CLI ok"
```

If `topics seeded` is `0`, run the seed one-liner from [USAGE.md](../USAGE.md) §4
first — the brief in step 2 depends on those rows existing.

---

## 2. Write the Theme Brief (`goal.md`)

Pick a short, stable **run id** (kebab-case) — it names the workspace directory
and is what you pass to the skill. Then author the brief:

```bash
mkdir -p harness/runs/invisible-systems
$EDITOR harness/runs/invisible-systems/goal.md
```

### The brief format

`goal.md` is front-matter (a tiny YAML-ish dialect) plus an optional body of
free notes to the Architect. Fields:

| Field | Required | Meaning |
| ----- | :------: | ------- |
| `through_line` | **yes** | the editorial spine of the whole run — the one idea every Piece serves |
| `target_topics` | **yes** | the Topics the constellation must span, as **exact seeded slugs** (list, ≥1) |
| `piece_count` | **yes** | a number (`4`) or a range (`4-6`) — the target Piece count |
| `seed_sources` | no | human-curated URLs — trusted tier, still vetted by the Researcher |
| `must_include` | no | angles the Architect must place in the plan |
| `entry_hints` | no | Pieces that should open cold as a Daily Feature |
| `must_avoid` | no | framings to keep out |
| `voice` | no | a Voice Profile name; omit to use the active default |
| *body* | no | free prose to the Architect, after the closing `---` |

Rules the Stage-0 gate enforces before any stage runs:

- **No placeholders.** Any `<like-this>` span fails the gate. Fill every field.
- **`target_topics` must be real seeded slugs.** They are not free text — the
  Architect tags Pieces with them and the write stage inserts them into
  `piece_topics`, which is foreign-keyed to `topics`. A typo or a made-up slug
  is caught at publish with `TopicNotFoundError`, and the atomic write means
  **nothing** is persisted. Copy slugs from §5 or list them live:

  ```bash
  uv run python -c "import os, psycopg; from dotenv import load_dotenv; load_dotenv(); \
  c=psycopg.connect(os.environ['DATABASE_URL']); \
  [print(r[0]) for r in c.execute('select id from topics order by id')]"
  ```

### Worked example — `harness/runs/invisible-systems/goal.md`

This uses four densely-interlocking slugs from the seeded V1 cluster, which
maximizes the high-value cross-Topic Connections the invariants reward.

```
---
through_line: >
  The invisible systems that move the physical world — a ship, a chip, a
  ledger, a strait — and how one failure in any of them cascades into all
  the others.
target_topics:
  - logistics-and-supply-chains
  - semiconductors
  - financial-systems
  - chokepoints-and-geography
piece_count: 4
entry_hints:
  - The container-shipping piece should open cold as a Daily Feature.
must_avoid:
  - breathless "this one weird system runs the world" framing
---

## Notes to the Architect

Lead with concrete objects — a ship, a chip, a ledger, a strait. Keep it
structural: each Piece should make the reader see a system they walk past
every day. Wire so no Piece is a dead end.
```

Everything after the closing `---` is free notes; keep it short and editorial.

---

## 3. Invoke the skill

With `goal.md` in place, start the conductor by naming the **run id**:

```
/new-constellation invisible-systems
```

The skill:

1. **Runs Stage 0** — verifies the Editorial DNA + active Voice Profile exist
   and that `harness/runs/invisible-systems/goal.md` is present, parses, and has
   no placeholders. If `goal.md` is missing, it **stops and tells you to author
   it** (per this guide) rather than inventing a brief.
2. **Reads `harness/manifest.toml` and the agent cards** and walks the stages in
   manifest order under the deliverable-on-disk prerequisite gate. Re-invoking
   with the same run id **resumes** from the first missing artifact.
3. **Delegates each stage to its subagent** — Architect → Researcher → Writer →
   Editor → Weaver → Reviewer — grounding through `harness fetch`, revising
   against `harness check-piece`, and asserting Tier-1 via
   `harness check-constellation`.

> **Resuming:** the run id *is* the resume key. `/new-constellation
> invisible-systems` a second time picks up where the workspace left off — done
> stages skip on their existing deliverables. Use `uv run harness status
> invisible-systems` any time for a read-only view of the pending gate.

---

## 4. The three human gates

The run pauses at three gates and asks for your decision in-session. At each,
the conductor shows you the artifact **plus** the relevant `harness check-*`
report so you decide with the contract result in hand.

| Gate | Fires after | You review | Scope |
| ---- | ----------- | ---------- | ----- |
| **plan** | the Architect (stage 1) | `plan.md` — concepts, Topic tags, the full Connection skeleton | whole run |
| **piece** | QA (stage 6) | each `pieces/<id>/piece.md` | **once per Piece** |
| **constellation** | publish-side re-QA | `publish/connections.md` — final wiring over survivors | whole run |

Your three moves at any gate:

- **Approve as-is** — accept the machine draft unchanged.
- **Edit-then-approve** — edit the working copy first; the CLI infers
  `edit_approve` from the preserved `*.machine.md → *.md` diff automatically.
  This is the richest signal the Distiller learns from.
- **Reject** — **requires a reason.** Rejected Pieces drop from the published
  set; the survivors carry forward.

The plan gate is the highest-leverage one — the editorial moat lives in the
plan. Spend your attention there.

The conductor records your decision through the seam (`harness verdict …`), so
verdicts are stamped `runtime=claude-code` — which is exactly why step 1.6
(`export HARNESS_RUNTIME=claude-code`) matters: without it the verdict is
mis-attributed to the production engine.

---

## 5. Publish and verify

After the constellation gate is approved, the conductor publishes:

```
uv run harness publish invisible-systems
```

`publish` re-wires and re-QAs the approved survivors and **atomically writes only
the re-validated set** to the Content Graph through the same write port
production uses. It **enforces the constellation gate itself**: with no approving
verdict it leaves `publish/connections.md` for review and exits `2`
(`awaiting verdict`) **without writing**. Exit `0` means the whole survivor set
published; a non-zero exit lists any Piece flagged back (only the valid set was
written).

Verify the run is really in the graph (indistinguishable from a DeepSeek-made
one):

```bash
# The published manifest the run wrote
cat harness/runs/invisible-systems/publish/published.json

# The Pieces are in Postgres, tagged with your seeded Topics
uv run python -c "import os, psycopg; from dotenv import load_dotenv; load_dotenv(); \
c=psycopg.connect(os.environ['DATABASE_URL']); \
[print(r) for r in c.execute('select piece_id, topic_id from piece_topics order by piece_id').fetchall()]"
```

---

## Reference — the seeded Topic slugs

These are the 29 slugs the V1 seed (`docs/taxonomy.md`) writes. Use these exact
strings in `target_topics`. Categories are roots; the rest are their
subcategories.

| Category (root slug) | Subcategory slugs |
| -------------------- | ----------------- |
| `engineering-and-infrastructure` | `logistics-and-supply-chains`, `energy-and-power`, `megaprojects`, `transport-systems`, `manufacturing` |
| `technology-and-computing` | `semiconductors`, `distributed-systems`, `cryptography-and-security`, `the-internets-plumbing`, `ai-ml` |
| `economics-and-markets` | `trade-and-globalization`, `behavioral-economics`, `game-theory`, `financial-systems`, `economic-history` |
| `geopolitics-and-power` | `chokepoints-and-geography`, `resource-politics`, `statecraft-and-intelligence`, `empire-and-decline` |
| `warfare-and-strategy` | `military-logistics`, `strategy-and-doctrine`, `weapons-tech`, `cyber-conflict` |

Two subcategories are **multi-parent** (the DAG earning its keep):
`behavioral-economics` also sits under `psychology-and-the-mind`, and
`cyber-conflict` also sits under `warfare-and-strategy`. `psychology-and-the-mind`
is seeded only as a bare parent (its own wave is deferred) — you *can* target it,
but there is little else under it yet, so prefer the V1 cluster above for dense
Connections.

> The list above is authoritative for the seed as documented. Always confirm
> against your live DB with the `select id from topics` query in §2 — that is
> the set the write stage validates against.

---

## Troubleshooting

| Symptom | Cause → fix |
| ------- | ----------- |
| `Brief requires target_topics` / `through_line` / `piece_count` | `goal.md` is missing a required field or isn't front-matter. Use the §2 template; the first line must be `---`. |
| `Brief has unfilled placeholders: <…>` | You left a `<placeholder>` in the brief. Fill it. |
| `TopicNotFoundError: … references a Topic that does not exist` at publish | A `target_topics` slug isn't seeded (typo, or a deferred-wave slug). Fix it against §5 / the live query. Nothing was written — the insert is atomic. |
| `run is new — pass a brief` / Stage 0 stops asking for `goal.md` | You invoked the skill for a run id with no `goal.md`. Author it first (§2), then re-invoke. |
| Verdicts show `runtime=langgraph` / a DeepSeek model | You didn't `export HARNESS_RUNTIME=claude-code` / `HARNESS_MODEL=…` before the run. Set them (step 1.6) and re-record. |
| `harness fetch` errors about a browser / executable | Playwright browser missing → `uv run playwright install chromium`. |
| `publish` exits `2` (`awaiting verdict`) | The constellation gate has no approving verdict yet — approve it, then re-run `publish`. This is the seam refusing to write, by design. |

---

## Why this is safe to run

Claude is forced through the identical `check-*` gates and the identical atomic
write as the production engine, so it **cannot publish an out-of-contract
constellation** any more than LangGraph can — same manifest, same specs, same
contract, same write. What differs is only the prose (a different model writes
it) and the verdict stamp (`runtime=claude-code`), which is exactly what lets the
Distiller tell the two engines apart. See
[ADR 0019](adr/0019-claude-code-generation-runtime-and-shared-harness-cli.md).
