"""Issue 10 — dual-runtime parity: same specs, same manifest, same behavior (ADR 0010)."""

import json

from tests.harness.fixture_run import PIECE_IDS, build_context

from harness.guardrails.constellation import evaluate_constellation
from harness.pipeline.context import HarnessConfig
from harness.pipeline.graph import run_pipeline
from harness.pipeline.stages import assemble_constellation
from harness.review.surface import WorkspaceVerdictGates, read_verdicts, record_verdict
from harness.runtimes.manifest_runner import run_manifest_pipeline

CC_CONFIG = HarnessConfig(runtime="claude-code", model="cc-scripted-fake")


def cast_verdict(ctx, gate_name, target_id, verdict="approve", reason=""):
    return record_verdict(
        ctx.workspace,
        ctx.manifest.human_gate(gate_name),
        target_id,
        verdict,
        run_id=ctx.run_id,
        runtime=ctx.config.runtime,
        model=ctx.config.model,
        reason=reason,
    )


def drive_to_completion(ctx, run):
    pauses = []
    while True:
        state = run(ctx)
        if state["status"] != "paused":
            return pauses, state
        detail = state["detail"]
        pauses.append(detail)
        remainder = detail.removeprefix("awaiting verdict at gate: ")
        gate_name, _, piece_id = remainder.partition(" ")
        if gate_name == "plan":
            working = ctx.workspace.read("plan.md")
            ctx.workspace.write("plan.md", working.replace("Waterfront", "Docks"))
        cast_verdict(ctx, gate_name, piece_id or gate_name)


def normalized_verdict_lines(workspace):
    lines = []
    for record in read_verdicts(workspace):
        payload = json.loads(record.to_json_line())
        for runtime_specific in ("ts", "runtime", "model"):
            payload.pop(runtime_specific)
        lines.append(payload)
    return lines


def test_both_runtimes_pause_review_and_publish_identically(tmp_path):
    lg = build_context(tmp_path / "lg", gates=WorkspaceVerdictGates())
    cc = build_context(tmp_path / "cc", gates=WorkspaceVerdictGates(), config=CC_CONFIG)

    lg_pauses, lg_state = drive_to_completion(lg, run_pipeline)
    cc_pauses, cc_state = drive_to_completion(cc, run_manifest_pipeline)

    assert lg_pauses == cc_pauses
    assert len(lg_pauses) == 2 + len(PIECE_IDS)
    assert lg_state["status"] == cc_state["status"] == "completed"
    assert sorted(lg_state["published"]) == sorted(cc_state["published"]) == sorted(PIECE_IDS)

    assert lg.workspace.read("plan.machine.md") == cc.workspace.read("plan.machine.md")
    assert normalized_verdict_lines(lg.workspace) == normalized_verdict_lines(cc.workspace)
    assert {r.runtime for r in read_verdicts(lg.workspace)} == {"langgraph"}
    assert {r.runtime for r in read_verdicts(cc.workspace)} == {"claude-code"}

    lg_plan = next(r for r in read_verdicts(lg.workspace) if r.gate == "plan")
    cc_plan = next(r for r in read_verdicts(cc.workspace) if r.gate == "plan")
    assert lg_plan.verdict == cc_plan.verdict == "edit_approve"
    assert lg_plan.edit_diff == cc_plan.edit_diff

    for ctx in (lg, cc):
        constellation = assemble_constellation(ctx, connections_source="publish/connections.md")
        report = evaluate_constellation(constellation, ctx.specs.banned_phrases())
        assert report.passed

    lg_read = [(s.id, s.title, s.teaser) for s in lg.repo.list_piece_summaries()]
    cc_read = [(s.id, s.title, s.teaser) for s in cc.repo.list_piece_summaries()]
    assert lg_read == cc_read


def test_rejection_semantics_are_identical_across_runtimes(tmp_path):
    outcomes = []
    runners = (
        ("lg", run_pipeline, None),
        ("cc", run_manifest_pipeline, CC_CONFIG),
    )
    for label, run, config in runners:
        ctx = build_context(tmp_path / label, gates=WorkspaceVerdictGates(), config=config)
        run(ctx)
        cast_verdict(ctx, "plan", "plan", verdict="reject", reason="the through-line is a listicle")
        state = run(ctx)
        outcomes.append((state["status"], state["detail"]))
    assert outcomes[0] == outcomes[1]
    assert outcomes[0][0] == "rejected"


def test_stage_zero_refusal_is_identical_across_runtimes(tmp_path):
    lg = build_context(tmp_path / "lg", goal="")
    cc = build_context(tmp_path / "cc", goal="", config=CC_CONFIG)
    lg_state = run_pipeline(lg)
    cc_state = run_manifest_pipeline(cc)
    assert lg_state["status"] == cc_state["status"] == "failed"
    assert lg_state["detail"] == cc_state["detail"]
