"""Issue 05 — bounded per-Piece concurrency + collect-all-failures routing.

Concurrency is an efficiency change only (byte-identical deliverables,
resume-skip preserved, the bound honored); a Piece that fails its edit bar is
collected — best-effort machine copy + failure code — and routed into the
piece gate, where an edit-approve fix (or a rejection) is the ordinary path.
"""

import json
import threading

from tests.harness.fixture_run import PIECE_IDS, build_context, well_behaved_llm

from harness.pipeline import stages
from harness.pipeline.context import HarnessConfig
from harness.pipeline.graph import run_pipeline
from harness.review.gates import GateDecision, GatePolicy, GateStatus
from harness.review.surface import WorkspaceVerdictGates, read_verdicts


def run_through_edit(ctx):
    stages.run_stage_plan(ctx)
    stages.run_stage_source(ctx)
    stages.run_stage_draft(ctx)
    stages.run_stage_edit(ctx)


def deliverables(ctx):
    out = {}
    for piece_id in PIECE_IDS:
        for path in (
            stages.grounding_path,
            stages.sources_path,
            stages.draft_path,
            stages.piece_path,
        ):
            out[path(piece_id)] = ctx.workspace.read(path(piece_id))
    return out


def test_fan_out_deliverables_are_byte_identical_to_serial(tmp_path):
    serial = build_context(tmp_path / "serial", config=HarnessConfig(fan_out=1))
    concurrent = build_context(tmp_path / "concurrent", config=HarnessConfig(fan_out=4))
    run_through_edit(serial)
    run_through_edit(concurrent)
    assert deliverables(serial) == deliverables(concurrent)


def test_resume_skips_pieces_whose_deliverable_already_exists(tmp_path):
    ctx = build_context(tmp_path, config=HarnessConfig(fan_out=4))
    run_through_edit(ctx)
    before = ctx.workspace.read(stages.piece_path("p-container"))
    requests_after_first = len(ctx.llm.requests)
    stages.run_stage_source(ctx)
    stages.run_stage_draft(ctx)
    stages.run_stage_edit(ctx)
    assert len(ctx.llm.requests) == requests_after_first
    assert ctx.workspace.read(stages.piece_path("p-container")) == before


def test_the_fan_out_bound_caps_concurrency_and_still_runs_every_item(tmp_path):
    ctx = build_context(tmp_path, config=HarnessConfig(fan_out=3))
    live = 0
    peak = 0
    done: list[int] = []
    lock = threading.Lock()
    release = threading.Event()

    def work(item):
        nonlocal live, peak
        with lock:
            live += 1
            peak = max(peak, live)
        release.wait(timeout=1.0)
        with lock:
            done.append(item)
            live -= 1

    releaser = threading.Thread(target=lambda: (threading.Event().wait(0.05), release.set()))
    releaser.start()
    stages._fan_out(ctx, list(range(12)), work)
    releaser.join()
    assert sorted(done) == list(range(12))
    assert peak <= 3


def collect_failure_ctx(tmp_path, gates):
    ctx = build_context(tmp_path, llm=well_behaved_llm(), gates=gates)

    def stubborn_agent(request, tools, step_limit):
        check = next(t for t in tools if t.name == "check_guardrails")
        candidate = {
            "title": request.payload["title"],
            "teaser": request.payload["teaser"],
            "read_time_min": request.payload["read_time_min"],
            "blocks": [dict(block) for block in request.payload["blocks"]],
        }
        if str(request.payload["piece_id"]) == "p-chip":
            candidate["blocks"][1]["text"] += " This proved to be a game-changer for the industry."
        check.run(candidate)
        return json.dumps(candidate)

    ctx.llm.on_agent("editor.qa", stubborn_agent)
    return ctx


class RejectFailed(GatePolicy):
    """Rejects the failed Piece at the piece gate; approves everything else."""

    def __init__(self, failed):
        self.failed = failed

    def decide(self, workspace, gate, target_id):
        if gate.per_piece and target_id in self.failed:
            return GateDecision(status=GateStatus.REJECTED, reason="unfixable machine copy")
        return GateDecision(status=GateStatus.APPROVED)


def test_edit_failure_finishes_the_others_and_is_persisted_with_its_code(tmp_path):
    ctx = collect_failure_ctx(tmp_path, gates=RejectFailed({"p-chip"}))
    run_through_edit(ctx)
    assert stages.has_failed(ctx, "p-chip")
    assert "QABudgetExceededError" in ctx.workspace.read(stages.failure_path("p-chip"))
    assert ctx.workspace.exists(stages.piece_path("p-chip"))
    for other in ("p-container", "p-money", "p-strait"):
        assert not stages.has_failed(ctx, other)
        assert ctx.workspace.exists(stages.piece_path(other))


def test_rejecting_the_failed_piece_yields_a_contract_valid_survivor_set(tmp_path):
    ctx = collect_failure_ctx(tmp_path, gates=RejectFailed({"p-chip"}))
    state = run_pipeline(ctx)
    assert state["status"] == "completed"
    published = sorted(state["published"])
    assert "p-chip" not in published
    assert published == ["p-container", "p-money", "p-strait"]
    assert ctx.repo.get_piece("p-chip") is None
    for piece_id in published:
        assert ctx.repo.get_piece(piece_id) is not None


def test_editapprove_fixing_the_failed_piece_keeps_it_a_survivor(tmp_path):
    ctx = collect_failure_ctx(tmp_path, gates=WorkspaceVerdictGates())
    state = run_pipeline(ctx)
    assert state["status"] == "paused"
    while state["status"] == "paused":
        detail = state["detail"].removeprefix("awaiting verdict at gate: ")
        gate_name, _, target = detail.partition(" ")
        target_id = target or gate_name
        if gate_name == "piece" and target_id == "p-chip":
            polished = ctx.workspace.read(stages.piece_path("p-chip")).replace(
                "Three Nanometres of Geography", "Three Nanometres of Geography, Revisited"
            )
            ctx.workspace.write(stages.piece_path("p-chip"), polished)
        from harness.review.surface import record_verdict

        record_verdict(
            ctx.workspace,
            ctx.manifest.human_gate(gate_name),
            target_id,
            "approve",
            run_id=ctx.run_id,
            runtime=ctx.config.runtime,
            model=ctx.config.model,
        )
        state = run_pipeline(ctx)
    assert state["status"] == "completed"
    assert "p-chip" in state["published"]
    piece_verdicts = [r for r in read_verdicts(ctx.workspace) if r.gate == "piece"]
    chip = next(r for r in piece_verdicts if r.target_id == "p-chip")
    assert chip.verdict == "edit_approve"
