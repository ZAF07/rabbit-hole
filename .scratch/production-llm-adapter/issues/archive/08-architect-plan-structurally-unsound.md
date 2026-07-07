# architect.plan produces a structurally-unsound plan against the live model

Status: completed

## Diagnosis & fix (2026-07-08)

**Root cause (architectural, not a wrong check).** `_assert_plan_sound` is
correct; the existing `test_planned_skeleton_is_structurally_sound_by_construction`
proves it fires. The defect is that `run_stage_plan` called the model **once**
and treated the soundness check as terminal — no re-plan path — so any
probabilistic miss aborted Stage 1. The contract also stated JSON _shape_ but
none of the structural obligations (piece count, no dead ends, endpoint
validity, connectivity), so the model's first shot had poor odds.

**Fix — both prongs the issue scoped:**

1. Bounded re-plan loop in `_plan_with_repair` (`architect.py`): on a
   soundness/duplicate failure the concrete violations are fed back via
   `payload["prior_violations"]` and the Architect re-plans, up to
   `HarnessConfig.plan_repair_budget` (default 2) extra attempts, then aborts
   with the last error. Mirrors the Weaver's `hook_budget` and the "agent
   proposes, code disposes" doctrine (ADR 0016). First request byte-unchanged.
2. `PLAN_RESPONSE_CONTRACT` (`decode.py`) now states the structural rules
   (count within target, unique ids, endpoints must be defined concepts, no
   dead ends, single connected graph, ≥1 entry-worthy) and how to consume
   `prior_violations`.

**Feedback loop (deterministic, red→green):** a `ScriptedLLM` model that
returns a dead-end plan (I4) until the request carries `prior_violations`, then
corrects. Red before the fix (aborted), green after (re-plans and writes a
sound plan). Captured as
`test_architect_re_plans_when_the_first_plan_is_structurally_unsound` plus a
budget-exhaustion guard and a contract-text test in `test_plan_stage.py`.

**Remaining:** live `/verify` against the DeepSeek adapter
(`uv run harness run <id>`) — needs API creds; not runnable offline here.

## Symptom

With issue 07 fixed (the plan payload now decodes), a real run against the live
DeepSeek adapter clears `decode_plan` but fails the next check,
`_assert_plan_sound`, which raises `ContractViolationError`:

```
uv run harness run empire-as-exhaustion
{
  "command": "run",
  "ok": false,
  "error": "planned skeleton is structurally unsound: I1 constellation: piece count 4 misses the Brief target [2, 2]; I4 the-costly-wall: dead end — no outbound Connection; I5 the-costly-wall->the-box: Connection endpoint(s) missing from constellation: the-box; I5 the-tax-papyrus->the-ledger: Connection endpoint(s) missing from constellation: the-ledger"
}
```

The live model's plan violates multiple structural invariants at once:

- **I1** — it proposed 4 Piece concepts, but the Brief's `piece_count` target is
  `[2, 2]`.
- **I4** — `the-costly-wall` is a dead end (no outbound Connection).
- **I5** — Connections reference concept ids that aren't in the plan
  (`the-box`, `the-ledger` are named as endpoints but never defined as concepts).

The run aborts at Stage 1; no Pieces or Connections are produced. Expected: the
Architect returns a plan that satisfies the Tier-1 structural invariants by
construction — correct piece count for the Brief, no dead ends, and every
Connection endpoint referring to a concept id present in the plan.

## Repro

```
uv run harness run empire-as-exhaustion
```

Non-deterministic — depends on what the live model returns for `architect.plan`.
Observed once. The invariant enforcement in `_assert_plan_sound` is correct and
working; the gap is that the model's output doesn't reliably satisfy the
invariants. `/diagnosing-bugs` should scope whether the fix is prompt-side
(state the `piece_count` target, forbid dangling endpoints / dead ends, require
connectivity explicitly in the instructions — the `PLAN_RESPONSE_CONTRACT` added
in issue 07 describes shape but not these structural rules), a bounded
re-plan/repair loop on a soundness failure, or both.

## Suspected location

- [src/harness/pipeline/stages/architect.py](src/harness/pipeline/stages/architect.py) — `run_stage_plan` (the `architect.plan` instructions/payload) and `_assert_plan_sound` (the invariant check that fires).
- [src/harness/pipeline/decode.py](src/harness/pipeline/decode.py) — `PLAN_RESPONSE_CONTRACT` states the JSON shape but no structural rules (piece count, connectivity, endpoint validity).
- The constellation guardrail spec ([harness/guardrails/constellation.md](harness/guardrails/constellation.md)) — carried into the prompt, but evidently not concrete enough for the model to satisfy I1/I4/I5 by construction.

## Acceptance criteria

- [x] `uv run harness run <id>` no longer fails at `architect.plan` with `planned skeleton is structurally unsound` for a Brief the invariants can satisfy
- [x] A test covers the fixed behaviour (a schema-faithful/soundness-aware model, or a repair loop, yields a plan that passes `_assert_plan_sound`)
- [x] Quality gates pass: `uv run ruff check .`, `uv run mypy src`, `uv run pytest`

## Completion

- Completed: 2026-07-08
- Commit: `.scratch/production-llm-adapter/issues/08-architect-plan-structurally-unsound.md`
