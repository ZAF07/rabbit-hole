"""Issue 07 — the human review surface (three gates, diff-by-preservation, verdicts.jsonl)."""

import dataclasses
import json

import pytest
from tests.harness.fixture_run import PIECE_IDS, build_context

from content_graph.domain.read_models import (
    ConnectionPreview,
    PieceRead,
    PieceSummary,
    TopicRead,
)
from harness.errors import MalformedArtifactError
from harness.pipeline.graph import run_pipeline
from harness.review.gates import GateStatus
from harness.review.surface import (
    VERDICTS_PATH,
    WorkspaceVerdictGates,
    read_verdicts,
    record_verdict,
)

REJECT_REASON = "premise is a rehash of the container piece"


def review_context(tmp_path):
    return build_context(tmp_path, gates=WorkspaceVerdictGates())


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


def walk_to_constellation_gate_with_rejection(ctx):
    run_pipeline(ctx)
    cast_verdict(ctx, "plan", "plan")
    run_pipeline(ctx)
    for piece_id in PIECE_IDS:
        if piece_id == "p-chip":
            cast_verdict(ctx, "piece", piece_id, verdict="reject", reason=REJECT_REASON)
        else:
            cast_verdict(ctx, "piece", piece_id)
    return run_pipeline(ctx)


def test_run_pauses_at_the_plan_gate_until_a_verdict_lands(tmp_path):
    ctx = review_context(tmp_path)
    state = run_pipeline(ctx)
    assert state["status"] == "paused"
    assert "plan" in state["detail"]
    assert ctx.workspace.exists("plan.machine.md")
    assert not ctx.workspace.exists("pieces/p-container/piece.md")


def test_verdicts_walk_the_run_through_all_three_gates(tmp_path):
    ctx = review_context(tmp_path)
    assert run_pipeline(ctx)["status"] == "paused"
    cast_verdict(ctx, "plan", "plan")

    state = run_pipeline(ctx)
    assert state["status"] == "paused"
    assert state["detail"] == "awaiting verdict at gate: piece p-container"
    assert ctx.workspace.exists("pieces/p-container/piece.machine.md")
    for piece_id in PIECE_IDS:
        cast_verdict(ctx, "piece", piece_id)

    state = run_pipeline(ctx)
    assert state["status"] == "paused"
    assert "constellation" in state["detail"]
    assert ctx.workspace.exists("publish/connections.machine.md")
    cast_verdict(ctx, "constellation", "constellation")

    state = run_pipeline(ctx)
    assert state["status"] == "completed"
    assert sorted(state["published"]) == sorted(PIECE_IDS)
    assert ctx.repo.get_piece("p-container") is not None


def test_pure_approval_is_recorded_as_approve_with_no_diff(tmp_path):
    ctx = review_context(tmp_path)
    run_pipeline(ctx)
    record = cast_verdict(ctx, "plan", "plan")
    assert record.verdict == "approve"
    assert record.edit_diff is None


def test_edited_working_copy_upgrades_approve_to_edit_approve(tmp_path):
    ctx = review_context(tmp_path)
    run_pipeline(ctx)
    working = ctx.workspace.read("plan.md")
    ctx.workspace.write("plan.md", working.replace("Waterfront", "Docks"))

    record = cast_verdict(ctx, "plan", "plan")

    assert record.verdict == "edit_approve"
    assert record.edit_diff is not None
    assert "--- plan.md (machine)" in record.edit_diff
    assert "+++ plan.md (human)" in record.edit_diff
    diff_lines = record.edit_diff.splitlines()
    assert any(line.startswith("-") and "Waterfront" in line for line in diff_lines)
    assert any(line.startswith("+") and "Docks" in line for line in diff_lines)
    assert "Waterfront" in ctx.workspace.read("plan.machine.md")
    assert read_verdicts(ctx.workspace)[-1].verdict == "edit_approve"


def test_every_line_carries_the_full_verdict_schema(tmp_path):
    ctx = review_context(tmp_path)
    run_pipeline(ctx)
    cast_verdict(ctx, "plan", "plan")
    run_pipeline(ctx)
    for piece_id in PIECE_IDS:
        cast_verdict(ctx, "piece", piece_id)

    lines = [json.loads(line) for line in ctx.workspace.read(VERDICTS_PATH).splitlines()]
    assert len(lines) == 1 + len(PIECE_IDS)
    expected_keys = {
        "ts",
        "run_id",
        "runtime",
        "model",
        "gate",
        "target_id",
        "verdict",
        "reason",
        "edit_diff",
        "topics",
    }
    for line in lines:
        assert set(line) == expected_keys
        assert line["run_id"] == "run-fixture"
        assert line["runtime"] == "langgraph"
        assert line["model"] == "scripted-fake"
        assert line["ts"]
    plan_line = lines[0]
    assert plan_line["gate"] == "plan"
    assert plan_line["target_id"] == "plan"
    assert plan_line["topics"] == [
        "chokepoints",
        "financial-systems",
        "logistics",
        "semiconductors",
    ]
    container_line = next(line for line in lines if line["target_id"] == "p-container")
    assert container_line["gate"] == "piece"
    assert container_line["topics"] == ["logistics"]


def test_a_reject_without_a_reason_is_refused(tmp_path):
    ctx = review_context(tmp_path)
    run_pipeline(ctx)
    with pytest.raises(MalformedArtifactError, match="requires a reason"):
        cast_verdict(ctx, "plan", "plan", verdict="reject")
    assert read_verdicts(ctx.workspace) == ()


def test_rejecting_the_plan_ends_the_run_with_the_reason(tmp_path):
    ctx = review_context(tmp_path)
    run_pipeline(ctx)
    cast_verdict(ctx, "plan", "plan", verdict="reject", reason="the through-line is a listicle")
    state = run_pipeline(ctx)
    assert state["status"] == "rejected"
    assert "listicle" in state["detail"]


def test_the_latest_verdict_for_a_target_wins(tmp_path):
    ctx = review_context(tmp_path)
    run_pipeline(ctx)
    cast_verdict(ctx, "plan", "plan", verdict="reject", reason="too diffuse")
    cast_verdict(ctx, "plan", "plan")
    decision = ctx.gates.decide(ctx.workspace, ctx.manifest.human_gate("plan"), "plan")
    assert decision.status is GateStatus.APPROVED
    assert len(read_verdicts(ctx.workspace)) == 2


def test_a_rejected_piece_is_excluded_from_the_published_set(tmp_path):
    ctx = review_context(tmp_path)
    state = walk_to_constellation_gate_with_rejection(ctx)
    assert state["status"] == "paused"
    assert "constellation" in state["detail"]
    assert state["rejected_pieces"] == ["p-chip"]
    assert state["survivors"] == ["p-container", "p-money", "p-strait"]

    cast_verdict(ctx, "constellation", "constellation")
    state = run_pipeline(ctx)
    assert state["status"] == "completed"
    assert sorted(state["published"]) == ["p-container", "p-money", "p-strait"]
    assert ctx.repo.get_piece("p-chip") is None
    assert ctx.repo.get_piece("p-container") is not None
    onward = {edge.to_piece_id for edge in ctx.repo.get_connections_from("p-container")}
    assert onward == {"p-money"}
    reject_record = next(r for r in read_verdicts(ctx.workspace) if r.verdict == "reject")
    assert reject_record.target_id == "p-chip"
    assert reject_record.reason == REJECT_REASON


def test_no_review_data_crosses_the_content_graph_boundary(tmp_path):
    ctx = review_context(tmp_path)
    walk_to_constellation_gate_with_rejection(ctx)
    cast_verdict(ctx, "constellation", "constellation")
    state = run_pipeline(ctx)
    assert state["status"] == "completed"

    generation_only = {"run_id", "verdict", "edit_diff", "reason", "gate", "ledger"}
    for model in (TopicRead, PieceSummary, ConnectionPreview, PieceRead):
        names = {field.name for field in dataclasses.fields(model)}
        assert not names & generation_only

    surface: list[object] = list(ctx.repo.list_piece_summaries())
    for piece_id in state["published"]:
        surface.append(ctx.repo.get_piece(piece_id))
        surface.extend(ctx.repo.get_connections_from(piece_id))
    blob = repr(surface)
    assert REJECT_REASON not in blob
    assert "verdicts.jsonl" not in blob
    assert "run-fixture" not in blob
