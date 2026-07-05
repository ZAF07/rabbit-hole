# Dual-runtime parity — Claude Code wiring + parity test (fast-follow)

Status: ready-for-agent
Feature: generation-harness
Blocked by: 08

## What to build

*(Fast-follow.)* V1 runs the **LangGraph runtime as authoritative** for the guarantee; this slice adds the **Claude Code subagent wiring** over the *same* markdown specs + stage manifest, and the **parity test** that keeps the two runtimes honest ([ADR 0010](../../../docs/adr/0010-content-generation-pipeline-architecture.md), [ADR 0013](../../../docs/adr/0013-human-review-surface-is-the-file-workspace.md)).

- Split each agent spec from `harness/agents/README.md` into its `.claude/agents/<name>.md` subagent; both runtimes read the same specs + one manifest, so only the orchestration wiring is written twice.
- The parity test asserts that, on the fixture Brief, both runtimes: (a) emit **contract-satisfying** output (I1–I8), and (b) **pause at the same three gates**, preserve the machine draft identically, and — given the same verdict + edit — append an **identical `verdicts.jsonl` line** (runtime/model aside) and compute the **same machine→human diff**.

## Acceptance criteria

- [ ] Both runtimes produce a constellation satisfying I1–I8 on the fixture Brief (prose may differ; the contract does not).
- [ ] Both pause at plan / Piece / wired-constellation gates at the same points.
- [ ] Given identical verdict + edit inputs, both append an identical `verdicts.jsonl` line (modulo `runtime`/`model`) and compute the same machine→human diff.
- [ ] A runtime-specific review path that would break parity is caught by the test.
- [ ] `ruff`, `mypy`, `pytest` pass.

## Blocked by

- generation-harness/issues/08 (the full pipeline incl. gates + publish to assert parity over)
