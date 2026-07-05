"""Issue 06 — Weaver (per-origin hooks) + Reviewer (I1–I8 binary, J1–J5 judged)."""

import json

import pytest
from tests.harness.fixture_run import FIXTURE_EDGES, build_context

from harness.domain.qa_report import parse_qa_outcome
from harness.domain.wiring import parse_connections
from harness.errors import ContractViolationError, QABudgetExceededError
from harness.pipeline import stages


def run_through_wire(ctx):
    stages.run_stage_plan(ctx)
    stages.run_stage_source(ctx)
    stages.run_stage_draft(ctx)
    stages.run_stage_edit(ctx)
    stages.run_stage_wire(ctx)


def test_every_planned_connection_is_realized_with_a_hook(tmp_path):
    ctx = build_context(tmp_path)
    run_through_wire(ctx)
    edges = parse_connections(ctx.workspace.read("connections.md"))
    planned_pairs = {(edge["from"], edge["to"]) for edge in FIXTURE_EDGES}
    realized_pairs = {(edge.from_piece_id, edge.to_piece_id) for edge in edges}
    assert realized_pairs == planned_pairs
    assert all(edge.hook and edge.rationale for edge in edges)


def test_identical_hook_across_origins_fails_and_is_regenerated(tmp_path):
    ctx = build_context(tmp_path)
    lure = "What the container did to the price of everything?"
    state = {"served_duplicate": False}

    def duplicating_hook(request):
        from tests.harness.fixture_run import _hook

        to_id = request.payload["to"]["id"]
        already_flagged = bool(request.payload["violations"])
        if to_id == "p-money" and not already_flagged:
            state["served_duplicate"] = True
            return json.dumps(
                {"hook": lure, "rationale": "The ledger is the box's shadow, precisely."}
            )
        return _hook(request)

    ctx.llm.on("weaver.hook", duplicating_hook)
    run_through_wire(ctx)
    edges = parse_connections(ctx.workspace.read("connections.md"))
    hooks_to_money = [edge.hook for edge in edges if edge.to_piece_id == "p-money"]
    assert state["served_duplicate"] is True
    assert len(hooks_to_money) == 2
    assert len(set(hooks_to_money)) == 2
    retried = [
        r for r in ctx.llm.requests if r.purpose == "weaver.hook" and r.payload["violations"]
    ]
    assert retried


def test_hook_that_never_passes_exhausts_the_budget_loud(tmp_path):
    ctx = build_context(tmp_path)
    ctx.llm.on(
        "weaver.hook",
        lambda r: json.dumps({"hook": "Learn more.", "rationale": "Both are about trade."}),
    )
    stages.run_stage_plan(ctx)
    stages.run_stage_source(ctx)
    stages.run_stage_draft(ctx)
    stages.run_stage_edit(ctx)
    with pytest.raises(QABudgetExceededError, match="connection"):
        stages.run_stage_wire(ctx)
    assert not ctx.workspace.exists("connections.md")


def test_wired_constellation_has_zero_dead_ends(tmp_path):
    ctx = build_context(tmp_path)
    run_through_wire(ctx)
    edges = parse_connections(ctx.workspace.read("connections.md"))
    origins = {edge.from_piece_id for edge in edges}
    assert origins == {"p-container", "p-chip", "p-money", "p-strait"}


def test_reviewer_records_binary_tier1_and_judged_tier2_in_qa_md(tmp_path):
    ctx = build_context(tmp_path)
    run_through_wire(ctx)
    escalations = stages.run_stage_qa(ctx)
    assert escalations == ()
    text = ctx.workspace.read("qa.md")
    passed, recorded = parse_qa_outcome(text)
    assert passed is True
    assert recorded == ()
    for code in ("I1", "I2", "I3", "I4", "I5", "I6", "I7", "I8"):
        assert f"- {code}: pass" in text
    for code in ("J1", "J2", "J3", "J4", "J5"):
        assert f"- {code}: pass" in text


def test_tier1_failure_fails_the_run_not_a_soft_warning(tmp_path):
    ctx = build_context(tmp_path)
    run_through_wire(ctx)
    wired = ctx.workspace.read("connections.md")
    tampered = "\n".join(
        line for line in wired.splitlines() if not line.startswith("- p-strait ->")
    )
    ctx.workspace.write("connections.md", tampered + "\n")
    with pytest.raises(ContractViolationError, match="I4"):
        stages.run_stage_qa(ctx)
    passed, _ = parse_qa_outcome(ctx.workspace.read("qa.md"))
    assert passed is False
    assert "- I4: FAIL" in ctx.workspace.read("qa.md")


def test_tier2_flags_are_escalated_not_silently_passed(tmp_path):
    ctx = build_context(tmp_path)

    def flag_duplicates(request):
        return json.dumps(
            {
                "judgements": [
                    {"code": "J1", "passed": True, "note": ""},
                    {"code": "J2", "passed": False, "note": "p-chip and p-money overlap"},
                    {"code": "J3", "passed": True, "note": ""},
                    {"code": "J4", "passed": True, "note": ""},
                    {"code": "J5", "passed": True, "note": ""},
                ]
            }
        )

    ctx.llm.on("reviewer.tier2", flag_duplicates)
    run_through_wire(ctx)
    escalations = stages.run_stage_qa(ctx)
    assert escalations == ("J2",)
    text = ctx.workspace.read("qa.md")
    assert "J2: FLAG — p-chip and p-money overlap" in text
    _, recorded = parse_qa_outcome(text)
    assert recorded == ("J2",)
