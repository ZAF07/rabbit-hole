# The human review surface is the file workspace; review is runtime-agnostic

[ADR 0004](0004-human-ratified-learning-loop.md) makes the human the **arbiter** — approving the plan and every Piece in V1, with each verdict and edit-diff captured as learning signal. [ADR 0010](0010-content-generation-pipeline-architecture.md) requires **dual-runtime parity** (LangGraph *and* Claude Code produce the same contract-satisfying outcome). [ADR 0012](0012-publish-gate-rewire-and-reqa-approved-subset.md) adds a re-wire + re-QA pass before publish. What was undesigned: **what the human reviews *on*, and how that stays parity-safe.** The risk this ADR closes: a Claude-Code-only review UI would silently break parity at the single most important step.

## Decision

**The review surface is the run's file workspace + a runtime-agnostic verdict contract — not a feature of either runtime.** Both runtimes write the same deliverables to the same `runs/<id>/` layout, pause at the same gates, preserve the machine draft the same way, and append to the same `verdicts.jsonl`. **Claude Code is the V1 front-end** over that shared substrate; a rendered web app is deferred ([fast-follow](../content-harness.md) once the consumption renderer exists).

**Three human gates in V1:**

| # | Gate | Reviews | When |
| --- | --- | --- | --- |
| 1 | **Plan** | Piece concepts + Connection skeleton + hook *angles* | after Stage 1 |
| 2 | **Piece** | each finished Piece (approve / edit / reject) | after Stage 6, per Piece |
| 3 | **Wired constellation** | realized hooks (where taste lives) + graph shape | after the re-wire + re-QA pass, before the write |

Gate 3 sits after [ADR 0012](0012-publish-gate-rewire-and-reqa-approved-subset.md)'s re-wire so the human's last look is at the *actual* published shape, and it puts human eyes on the taste-critical hook copy without a per-hook load.

**Diff by preservation.** The machine's output is kept (`plan.machine.md`, `pieces/<id>/piece.machine.md`, `connections.machine.md`); the human edits the working copy; on approval the surface records the **unified machine→human diff** — the richest learning signal ([ADR 0004](0004-human-ratified-learning-loop.md): "machine wrote X, human changed it to Y"). File-based, so it is identical under either runtime.

**Verdict schema** (`feedback/verdicts.jsonl`, append-only) — one line per gate action:
`ts, run_id, runtime, model, gate (plan|piece|constellation), target_id, verdict (approve|edit_approve|reject), reason, edit_diff (unified; null if none), topics[]`.
`runtime` + `model` are recorded precisely *because* both runtimes share the workflow — so calibration can tell whether a signal is runtime-invariant. This corpus feeds the Distiller and per-Topic calibration.

**Parity covers review.** [ADR 0010](0010-content-generation-pipeline-architecture.md)'s parity now includes the human gates: same gate points, same preserved-draft mechanism, same verdict schema. The parity test asserts it — not just that both runtimes emit contract-satisfying output, but that they **pause and capture verdicts identically**.

## Why
- **Parity or bust.** If review were a runtime feature, the two runtimes would diverge at the step that decides quality. Making it the shared file workspace guarantees they can't.
- **Buildable now.** It reuses the we-os "markdown + files on disk" discipline the founder already trusts; no UI to build before the first ~30 Pieces.
- **Taste on the taste-critical copy.** Gate 3 reviews realized hooks — the line [CONTEXT.md](../CONTEXT.md) calls "where editorial taste lives" — instead of shipping them on machine QA alone.

## Trade-off
V1 review is **raw** (Content Blocks / markdown), not the rendered reader view — reader-fidelity preview is a deliberate fast-follow that *reuses* the consumption renderer rather than duplicating it. And three gates is more human touch than two; accepted for the first ~30 Pieces, where no slop leak is affordable. A per-hook gate was rejected as too heavy; a bespoke web app was rejected as premature.

## Consequence
The review surface + verdict contract are **shared substrate**; a runtime-specific review path that breaks parity is forbidden. Governs generation only — verdicts, diffs, and the review workspace never cross the [ADR 0006](0006-generation-and-consumption-are-separate.md) boundary; only the approved Pieces, Connections, and Topics do.
