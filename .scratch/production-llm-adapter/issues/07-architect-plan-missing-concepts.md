# architect.plan fails with "malformed plan payload: 'concepts'" on a real run

Status: needs-triage

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

- [ ] `uv run harness run <id>` no longer fails at `architect.plan` with `malformed plan payload: 'concepts'`
- [ ] A test covers the fixed behaviour (contract between the Architect response and `decode_plan`)
- [ ] Quality gates pass: `uv run ruff check .`, `uv run mypy src`, `uv run pytest`
