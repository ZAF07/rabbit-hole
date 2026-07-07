# architect.plan fails with "malformed plan payload: 'concepts'" on a real run

Status: completed

## Root cause (diagnosed)

The `architect.plan` prompt never stated the output JSON contract. Its
instructions were DNA + connection/constellation guardrails + taxonomy — all
editorial-quality specs — and the human turn only said "Respond with a single
JSON object." The wire schema (`concepts`/`connections` and the field names
`id`/`title`/`premise`/`topics`/`entry_worthy`, `from`/`to`/`hook_angle`/
`rationale`) lived **only** in `decode_plan`; nothing told the model. A
schema-blind-but-obedient model invents plausible keys (e.g. `pieces`/`edges`),
and `decode_plan` KeyErrors on `payload["concepts"]`.

Tests never caught it because the `_architect_plan` fixture hand-builds the
exact `concepts`/`connections` shape — the fixture "knows" a schema the prompt
never communicated.

Fix: `PLAN_RESPONSE_CONTRACT` (single-sourced next to `decode_plan` in
[src/harness/pipeline/decode.py](src/harness/pipeline/decode.py), the shape
authority) is now appended to the `architect.plan` instructions in
[src/harness/pipeline/stages/architect.py](src/harness/pipeline/stages/architect.py).

Regression test: `test_architect_prompt_states_the_plan_response_contract`
drives the real `run_stage_plan` with a schema-faithful fake that emits the
decoder's keys only if the prompt names them — red before the fix (exact
`malformed plan payload: 'concepts'`), green after.

**Broader finding (follow-up):** every other stage shares this defect — none of
`writer.draft`, `editor.*`, `weaver.hook`, `reviewer.tier2`, `researcher.*`
states its output contract in the prompt; their fixtures mask it exactly as the
Architect's did. A live run would now clear `architect.plan` and fail at the
next stage. Recommend filing a follow-up to give each decoder a
`*_RESPONSE_CONTRACT` and wire it into that stage's instructions.

## Symptom

Running a real generation run against the live LLM adapter fails at the plan stage:

```
uv run harness run empire-as-exhaustion
{
  "command": "run",
  "ok": false,
  "error": "architect.plan: malformed plan payload: 'concepts'"
}
```

The error is a `KeyError: 'concepts'` raised in
[src/harness/pipeline/decode.py:73](src/harness/pipeline/decode.py#L73) — `decode_plan`
accesses `payload["concepts"]`, but the JSON the Architect returned has no
`concepts` key. The run aborts at the first stage; no Pieces or Connections are
produced.

Expected: the Architect's plan payload contains a `concepts` array (and a
`connections` array) so `decode_plan` can build the `ConstellationPlan`.

## Repro

```
uv run harness run empire-as-exhaustion
```

Not yet confirmed deterministic — it depends on what the live model returns.
Likely the DeepSeek adapter's `architect.plan` response isn't conforming to the
expected schema (wrong top-level shape, wrapped/renamed key, or non-JSON
prose the loader mis-parsed). Root-causing is `/diagnosing-bugs`' job.

## Suspected location

- [src/harness/pipeline/decode.py:52-63](src/harness/pipeline/decode.py#L52-L63) — `decode_plan` requires a top-level `concepts` array.
- The Architect stage prompt / DeepSeek adapter response for `architect.plan` — whatever produces the payload that reaches `decode_plan`.

## Acceptance criteria

- [x] `uv run harness run <id>` no longer fails at `architect.plan` with `malformed plan payload: 'concepts'` — the prompt now carries `PLAN_RESPONSE_CONTRACT`; Phase-1 loop green.
- [x] A test covers the fixed behaviour (contract between the Architect response and `decode_plan`) — `test_architect_prompt_states_the_plan_response_contract`, red-before/green-after.
- [x] Quality gates pass: `uv run ruff check .` (clean), `uv run mypy src` (105 files, no issues), `uv run pytest` (396 passed, 1 skipped).

## Completion

- Completed: 2026-07-08
- Commit: `5ba705a2da047a900a0f587048cd1c3410932ccc`
