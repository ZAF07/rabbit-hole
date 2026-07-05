# Distiller — the human-ratified learning loop (out-of-band, fast-follow)

Status: completed
Feature: generation-harness
Blocked by: 07

## What to build

_(Fast-follow / out-of-band — not a per-run stage.)_ The batched learning loop that turns captured verdicts into proposed improvements to the taste artifacts, with the human ratifying every change ([ADR 0004](../../../docs/adr/0004-human-ratified-learning-loop.md)).

- A separate batched entry point (not in the per-run pipeline) that reads `feedback/verdicts.jsonl` + edit-diffs accumulated across runs.
- Batch-analyzes them and **proposes a markdown diff** to DNA / guardrails / exemplars: banned-phrase additions from repeated deletions, new checks from repeated reject reasons, exemplar promotions, DNA tweaks.
- Records the per-Topic **machine-vs-human agreement** signal so gate relaxation toward sampling can later be **data-gated per Topic** (relaxation itself stays manual/out-of-scope).
- **Nothing auto-merges** — every diff is presented to the human; only human-ratified diffs land.

## Acceptance criteria

- [x] Given a fixture `verdicts.jsonl` with repeated deletions of a phrase, the Distiller **proposes** adding it to the banned list — as a diff, not an applied change.
- [x] Given repeated reject reasons, it proposes a new check.
- [x] No artifact (DNA / guardrail / exemplar) is mutated without an explicit ratify step; the proposal is inert until ratified.
- [x] Per-Topic agreement counts are computed from the verdict corpus.
- [x] `ruff`, `mypy`, `pytest` pass.

## Blocked by

- generation-harness/issues/07 (the `verdicts.jsonl` corpus + edit-diffs it distills)

## Completion

- Completed: 2026-07-05
- Commit: `7af81e040b8b2425c330f3f874ccc206be43fe85`
