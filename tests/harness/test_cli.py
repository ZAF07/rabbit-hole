"""The shared ``harness`` CLI seam (ADR 0019) — exit code + stdout + side-effects.

These tests drive :func:`harness.cli.run_cli` in-process over the offline
fixture substrate (``build_context``, ``well_behaved_llm``,
``InMemoryContentGraphRepository``). They assert only externally observable
behavior — the exit code, the structured JSON on stdout, and the effect on the
run workspace / in-memory repo — never re-testing what ``evaluate_piece`` or the
publish steps already guarantee (those have their own tests).
"""

import io
import json

from tests.harness.fixture_run import (
    FIXTURE_GOAL,
    PIECE_IDS,
    build_context,
    hub_url,
    primary_url,
    secondary_url,
)
from tests.harness.pipeline.test_publish_gate import RETURN_EDGE_HOOK, llm_with_return_edge

from harness.cli import CliDeps, run_cli
from harness.pipeline import stages
from harness.review.gates import GateStatus
from harness.review.surface import WorkspaceVerdictGates, read_verdicts, record_verdict

SLOP_PIECE = """---
id: p-container
title: The Box
teaser: A teaser about the box and the trade that followed it downstream.
read_time_min: 4
topics: logistics
---

Here are three reasons the container changed the whole of world trade forever.

In conclusion, the box really did matter more than anyone expected at the time.
"""


def populated_context(tmp_path):
    """Run the fixture pipeline through Wire so the workspace holds every deliverable."""
    ctx = build_context(tmp_path)
    stages.run_stage_plan(ctx)
    stages.run_stage_source(ctx)
    stages.run_stage_draft(ctx)
    stages.run_stage_edit(ctx)
    stages.run_stage_wire(ctx)
    return ctx


def deps_for(ctx) -> CliDeps:
    """A CliDeps pointing at the context's run workspace, specs, and web port."""
    return CliDeps(
        runs_root=ctx.workspace.root.parent,
        specs=ctx.specs,
        config=ctx.config,
        web=ctx.web,
    )


def populated_through_qa(tmp_path, llm=None, gates=None):
    """Run the fixture pipeline through Constellation QA (ready to publish)."""
    ctx = build_context(tmp_path, llm=llm, gates=gates)
    stages.run_stage_plan(ctx)
    stages.run_stage_source(ctx)
    stages.run_stage_draft(ctx)
    stages.run_stage_edit(ctx)
    stages.run_stage_wire(ctx)
    stages.run_stage_qa(ctx)
    return ctx


def full_deps_for(ctx) -> CliDeps:
    """A CliDeps wired with every port from the fixture context."""
    return CliDeps(
        runs_root=ctx.workspace.root.parent,
        specs=ctx.specs,
        config=ctx.config,
        web=ctx.web,
        llm=ctx.llm,
        repo=ctx.repo,
        gates=ctx.gates,
    )


def reject_piece(ctx, piece_id, reason="cut by the fixture human"):
    """Record a per-piece reject verdict directly against the workspace."""
    record_verdict(
        ctx.workspace,
        ctx.manifest.human_gate("piece"),
        piece_id,
        "reject",
        run_id=ctx.run_id,
        runtime=ctx.config.runtime,
        model=ctx.config.model,
        reason=reason,
    )


def approve_constellation(ctx):
    """Record an approving constellation-gate verdict directly against the workspace."""
    record_verdict(
        ctx.workspace,
        ctx.manifest.human_gate("constellation"),
        "constellation",
        "approve",
        run_id=ctx.run_id,
        runtime=ctx.config.runtime,
        model=ctx.config.model,
    )


def invoke(deps, *argv):
    """Drive run_cli, returning (exit_code, parsed_stdout)."""
    out = io.StringIO()
    code = run_cli(argv, deps=deps, stdout=out)
    return code, json.loads(out.getvalue())


def test_check_piece_on_a_clean_piece_exits_zero_with_no_violations(tmp_path):
    ctx = populated_context(tmp_path)
    code, payload = invoke(deps_for(ctx), "check-piece", ctx.run_id, "p-container")
    assert code == 0
    assert payload["ok"] is True
    assert payload["piece_id"] == "p-container"
    assert payload["violations"] == []


def test_check_piece_on_a_slop_draft_exits_nonzero_and_lists_the_codes(tmp_path):
    ctx = populated_context(tmp_path)
    ctx.workspace.write(stages.piece_path("p-container"), SLOP_PIECE)
    code, payload = invoke(deps_for(ctx), "check-piece", ctx.run_id, "p-container")
    assert code == 1
    assert payload["ok"] is False
    codes = {violation["code"] for violation in payload["violations"]}
    assert {"D1", "D5"} <= codes


def test_check_piece_on_a_missing_piece_reports_a_structured_error(tmp_path):
    ctx = populated_context(tmp_path)
    code, payload = invoke(deps_for(ctx), "check-piece", ctx.run_id, "p-nonesuch")
    assert code == 2
    assert payload["ok"] is False
    assert "error" in payload


def test_check_constellation_on_the_clean_run_exits_zero(tmp_path):
    ctx = populated_context(tmp_path)
    code, payload = invoke(deps_for(ctx), "check-constellation", ctx.run_id)
    assert code == 0
    assert payload["ok"] is True
    assert payload["failed"] == []
    assert all(payload["results"].values())


def test_check_constellation_with_a_dead_end_names_the_failing_invariant(tmp_path):
    ctx = populated_context(tmp_path)
    connections = ctx.workspace.read(stages.CONNECTIONS)
    surviving = "\n".join(
        line for line in connections.splitlines() if not line.strip().startswith("- p-container ->")
    )
    ctx.workspace.write(stages.CONNECTIONS, surviving + "\n")

    code, payload = invoke(deps_for(ctx), "check-constellation", ctx.run_id)
    assert code == 1
    assert payload["ok"] is False
    assert "I4" in payload["failed"]
    assert payload["results"]["I4"] is False


def test_fetch_returns_the_canned_page_content_and_outlinks(tmp_path):
    ctx = build_context(tmp_path)
    url = hub_url("p-container")
    code, payload = invoke(deps_for(ctx), "fetch", url)
    assert code == 0
    assert payload["ok"] is True
    assert payload["page"]["url"] == url
    assert "Ideal-X" in payload["page"]["content"]
    assert set(payload["page"]["outlinks"]) == {
        primary_url("p-container"),
        secondary_url("p-container"),
    }


def test_fetch_on_an_unfetchable_url_signals_retry_and_exits_nonzero(tmp_path):
    ctx = build_context(tmp_path)
    code, payload = invoke(deps_for(ctx), "fetch", "https://nowhere.example/void")
    assert code == 2
    assert payload["ok"] is False
    assert payload["page"] is None


def test_verdict_approve_makes_the_gate_read_approved(tmp_path):
    ctx = populated_context(tmp_path)
    code, payload = invoke(deps_for(ctx), "verdict", ctx.run_id, "--gate", "plan", "--approve")
    assert code == 0
    assert payload["verdict"] == "approve"

    decision = WorkspaceVerdictGates().decide(
        ctx.workspace, ctx.manifest.human_gate("plan"), "plan"
    )
    assert decision.status is GateStatus.APPROVED


def test_verdict_reject_without_a_reason_errors_and_records_nothing(tmp_path):
    ctx = populated_context(tmp_path)
    code, payload = invoke(deps_for(ctx), "verdict", ctx.run_id, "--gate", "plan", "--reject")
    assert code == 2
    assert payload["ok"] is False
    assert read_verdicts(ctx.workspace) == ()


def test_verdict_reject_with_a_reason_records_the_reason(tmp_path):
    ctx = populated_context(tmp_path)
    code, payload = invoke(
        deps_for(ctx),
        "verdict",
        ctx.run_id,
        "--gate",
        "plan",
        "--reject",
        "--reason",
        "the through-line is too diffuse",
    )
    assert code == 0
    assert payload["verdict"] == "reject"
    assert payload["reason"] == "the through-line is too diffuse"


def test_verdict_on_an_edited_working_copy_is_recorded_as_edit_approve(tmp_path):
    ctx = populated_context(tmp_path)
    ctx.workspace.preserve_machine_copy("plan.md")
    plan = ctx.workspace.read("plan.md")
    ctx.workspace.write("plan.md", plan.replace("Waterfront", "Docks"))

    code, payload = invoke(deps_for(ctx), "verdict", ctx.run_id, "--gate", "plan", "--approve")
    assert code == 0
    assert payload["verdict"] == "edit_approve"
    assert payload["edit_diff"] is not None
    assert "Docks" in payload["edit_diff"]


def test_the_per_piece_gate_requires_a_target(tmp_path):
    ctx = populated_context(tmp_path)
    code, payload = invoke(deps_for(ctx), "verdict", ctx.run_id, "--gate", "piece", "--approve")
    assert code == 2
    assert payload["ok"] is False


def test_the_per_piece_gate_records_against_its_target(tmp_path):
    ctx = populated_context(tmp_path)
    code, payload = invoke(
        deps_for(ctx),
        "verdict",
        ctx.run_id,
        "--gate",
        "piece",
        "--target",
        "p-container",
        "--approve",
    )
    assert code == 0
    assert payload["target_id"] == "p-container"
    decision = WorkspaceVerdictGates().decide(
        ctx.workspace, ctx.manifest.human_gate("piece"), "p-container"
    )
    assert decision.status is GateStatus.APPROVED


def test_publish_writes_the_full_survivor_set(tmp_path):
    ctx = populated_through_qa(tmp_path)
    code, payload = invoke(full_deps_for(ctx), "publish", ctx.run_id)
    assert code == 0
    assert payload["ok"] is True
    assert sorted(payload["published"]) == sorted(PIECE_IDS)
    assert payload["flagged"] == []
    for piece_id in PIECE_IDS:
        assert ctx.repo.get_piece(piece_id) is not None


def test_publish_excludes_a_rejected_piece(tmp_path):
    ctx = populated_through_qa(tmp_path)
    reject_piece(ctx, "p-chip")
    code, payload = invoke(full_deps_for(ctx), "publish", ctx.run_id)
    assert code == 0
    assert sorted(payload["published"]) == ["p-container", "p-money", "p-strait"]
    assert ctx.repo.get_piece("p-chip") is None


def test_publish_flags_an_unfixable_survivor_and_exits_nonzero(tmp_path):
    ctx = populated_through_qa(tmp_path, llm=llm_with_return_edge())
    reject_piece(ctx, "p-strait")
    code, payload = invoke(full_deps_for(ctx), "publish", ctx.run_id)
    assert code == 1
    assert payload["ok"] is False
    assert payload["flagged"] == ["p-money"]
    assert sorted(payload["published"]) == ["p-chip", "p-container"]
    assert ctx.repo.get_piece("p-money") is None
    hooks = {edge.hook for edge in ctx.repo.get_connections_from("p-chip")}
    assert hooks == {RETURN_EDGE_HOOK}


def test_publish_dies_loud_when_no_valid_survivor_set_remains(tmp_path):
    ctx = populated_through_qa(tmp_path)
    reject_piece(ctx, "p-container")
    reject_piece(ctx, "p-chip")
    code, payload = invoke(full_deps_for(ctx), "publish", ctx.run_id)
    assert code == 2
    assert payload["ok"] is False
    assert ctx.repo.list_piece_summaries() == ()


def test_publish_refuses_to_write_without_a_constellation_verdict(tmp_path):
    ctx = populated_through_qa(tmp_path, gates=WorkspaceVerdictGates())
    code, payload = invoke(full_deps_for(ctx), "publish", ctx.run_id)
    assert code == 2
    assert payload["ok"] is False
    assert payload["status"] == "pending"
    assert ctx.repo.list_piece_summaries() == ()


def test_publish_writes_once_the_constellation_gate_is_approved(tmp_path):
    ctx = populated_through_qa(tmp_path, gates=WorkspaceVerdictGates())
    approve_constellation(ctx)
    code, payload = invoke(full_deps_for(ctx), "publish", ctx.run_id)
    assert code == 0
    assert payload["ok"] is True
    assert sorted(payload["published"]) == sorted(PIECE_IDS)


def test_run_seeds_goal_and_reports_the_paused_plan_gate(tmp_path):
    ctx = build_context(tmp_path, goal="", run_id="fresh", gates=WorkspaceVerdictGates())
    deps = full_deps_for(ctx)
    code, payload = invoke(deps, "run", "fresh", "--brief", FIXTURE_GOAL)
    assert code == 0
    assert payload["status"] == "paused"
    assert "plan" in payload["detail"]
    assert ctx.workspace.exists(stages.GOAL)


def test_run_resumes_past_a_recorded_verdict(tmp_path):
    ctx = build_context(tmp_path, goal="", run_id="fresh", gates=WorkspaceVerdictGates())
    deps = full_deps_for(ctx)
    invoke(deps, "run", "fresh", "--brief", FIXTURE_GOAL)
    invoke(deps, "verdict", "fresh", "--gate", "plan", "--approve")
    code, payload = invoke(deps, "run", "fresh")
    assert code == 0
    assert payload["status"] == "paused"
    assert "piece" in payload["detail"]


def test_run_on_a_new_run_without_a_brief_errors(tmp_path):
    ctx = build_context(tmp_path, goal="", run_id="fresh", gates=WorkspaceVerdictGates())
    code, payload = invoke(full_deps_for(ctx), "run", "fresh")
    assert code == 2
    assert payload["ok"] is False


def test_status_reports_the_pending_gate_without_mutating(tmp_path):
    ctx = build_context(tmp_path, goal="", run_id="fresh", gates=WorkspaceVerdictGates())
    deps = full_deps_for(ctx)
    invoke(deps, "run", "fresh", "--brief", FIXTURE_GOAL)

    before = sorted(p.name for p in ctx.workspace.root.rglob("*"))
    code, payload = invoke(deps, "status", "fresh")
    after = sorted(p.name for p in ctx.workspace.root.rglob("*"))
    assert code == 0
    assert payload["status"] == "paused"
    assert "plan" in payload["detail"]
    assert before == after


def test_status_reports_completed_after_publish(tmp_path):
    ctx = populated_through_qa(tmp_path)
    invoke(full_deps_for(ctx), "publish", ctx.run_id)
    code, payload = invoke(full_deps_for(ctx), "status", ctx.run_id)
    assert code == 0
    assert payload["status"] == "completed"


def test_unknown_subcommand_exits_nonzero(tmp_path):
    ctx = populated_context(tmp_path)
    out = io.StringIO()
    code = run_cli(["frobnicate"], deps=deps_for(ctx), stdout=out)
    assert code != 0
