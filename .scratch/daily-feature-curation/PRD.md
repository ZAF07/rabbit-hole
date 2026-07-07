# PRD: Daily Feature curation — promoting a published Piece to the app's front door

Status: needs-info
Feature: daily-feature-curation
Depends on: `content-graph` (the `daily_features` table, `set_daily_feature` / `get_daily_feature` on the `ContentGraphRepository` port — all shipped) and `consumption-app` (the reader's `/daily` + `/notification` endpoints that read the current Daily Feature — all shipped)

> **This PRD is a high-level stub, deliberately parked at `needs-info`.** The design was opened with `/grill-with-docs` and paused after the root decision. It captures the problem, the one locked decision, and the open branches so the grill can resume exactly where it stopped. Do not implement from this yet — it is not `ready-for-agent`.
>
> Boundary note: the Daily Feature is a **consumption / curatorial concern**, not a generation one ([ADR 0006](../../docs/adr/0006-generation-and-consumption-are-separate.md)) — generation "knows nothing about the app," and the Daily Feature *is* the app's front door. So whatever surface owns assignment must keep the harness out of it.

## Problem Statement

After a successful generation run, `harness publish <run>` durably writes a constellation's Pieces, Content Blocks, Topic tags, and Connections to the Content Graph — but **nothing ever populates `daily_features`**. The only writer of that table, `set_daily_feature`, is called solely from tests and a consumption fixture; no code path in the harness, the API/admin layer, or any scheduler assigns a Daily Feature in a real deployment.

The consequence is that a freshly published constellation is **unreachable to readers**. The reader's entry is guarded: `enter_piece` allows opening only the current Daily Feature or a Piece already in the reader's trail — there is no free-roam read (user story 12). With `daily_features` empty, `/daily` returns 404, and every downstream Piece is unreachable because the front door was never opened. Content can be perfectly published and still invisible.

## Solution (high-level direction)

Introduce the missing **curatorial act** that assigns which published Piece leads on a given day — a decision distinct from publishing, owned by a human/editorial surface rather than the pipeline. The resolution semantics already exist and are *not* being changed: the current Daily Feature is the most recently assigned Piece **on or before** today; an unassigned day inherits the prior assignment; a future-dated assignment is not surfaced early (see `CONTEXT.md` → *Daily Feature*).

The shape of that surface (admin endpoint vs. CLI vs. other), its eligibility rules, and its scheduling model are **still open** — see below.

## Decided so far

1. **Assignment is a separate curatorial act, not a `publish` side effect.** Publish makes a Piece *eligible* to lead; a distinct curatorial act makes it *featured*. Rationale: the glossary already frames the Daily Feature as "a curation/scheduling role," the product's stated moat is **editorial taste**, and "what leads today" is the most editorial decision in the app — it should not be a silent side effect of the pipeline, and it respects that a Constellation is "the unit of planning and QA, **never of consumption**."

## Open questions — resume the grill here

The grill paused at Q2. Outstanding branches, roughly in dependency order:

2. **Where does the curatorial surface live?** Leading (unconfirmed) recommendation: an admin/curation endpoint on the one backend deployable (e.g. `POST /admin/curation/daily-feature`), gated by the existing operator secret (`X-Admin-Token`), calling `content.set_daily_feature(on, piece_id)` through the Content Graph port — and, unlike the generation-trigger router, **live whenever `API_ADMIN_TOKEN` is set, independent of `generation_configured()`** (a reader-only deployment still needs to pick today's feature). Alternatives considered: a `harness feature` CLI verb (rejected-leaning — couples generation to an app concept) or a standalone curation script. **Awaiting the operator's decision.**
3. **What makes a Piece eligible to be assigned?** Must it be published/present in the Content Graph? Must it be entry-worthy (the generation J3 guardrail / `entry_hints`)? Is eligibility validated at assignment time, and what happens on assigning an unknown or unpublished `piece_id`?
4. **Scheduling model.** Assign-for-a-date (supporting scheduling ahead, which the read model already allows) vs. assign-for-today only. One Piece per day (the table is keyed by date). Re-assignment / overwrite semantics; is there an un-assign?
5. **Lifecycle coupling.** What happens to a date's pointer if the featured Piece is later unpublished or removed? Does the "inherit previous day" fallback cover gaps acceptably, or is an explicit guard needed?
6. **Bootstrapping.** The very first Daily Feature in a fresh deployment; how the `invisible-systems` constellation (already published) gets its first assignment.
7. **Verification & testing seams.** Where the behavior is tested (prior art: `tests/contract/test_daily_feature.py` for the adapter; consumption reader tests for `/daily`), and how it is verified end-to-end in the running system.

## Out of scope (provisional)

- Changing the Daily Feature *resolution* semantics (on-or-before, inherit-previous, no-future-early) — settled and unchanged.
- Auto-selection / rotation policy for *which* Piece leads (a scheduler) — a separate future decision if a human-in-the-loop act proves insufficient.
- Any change to the generation pipeline's output contract.

## Further notes

Discovered while verifying the publish-durability fix ([.scratch/content-graph/issues/archive/06-publish-write-rolled-back-no-commit.md](../content-graph/issues/archive/06-publish-write-rolled-back-no-commit.md)): with publish now durable, `invisible-systems`' two Pieces (`the-box`, `the-ledger`), 23 Content Blocks, topic tags, and 2 Connections are all present in Postgres, yet `/daily` still has nothing to serve because `daily_features` is empty — which is what surfaced this gap.
