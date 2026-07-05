"""Issue 08 — the publish gate: re-wire, re-QA with flagging, atomic write (ADR 0012)."""

import json

import pytest
from tests.harness.fixture_run import PIECE_IDS, build_context, well_behaved_llm

from harness.errors import PublishIntegrityError
from harness.pipeline import publish, stages
from harness.pipeline.graph import run_pipeline
from harness.review.gates import GateDecision, GatePolicy, GateStatus


class ScriptedGates(GatePolicy):
    def __init__(self, reject=frozenset(), pending=frozenset()):
        self.reject = frozenset(reject)
        self.pending = frozenset(pending)

    def decide(self, workspace, gate, target_id):
        if target_id in self.pending:
            return GateDecision(status=GateStatus.PENDING)
        if target_id in self.reject:
            return GateDecision(status=GateStatus.REJECTED, reason="cut by the fixture human")
        return GateDecision(status=GateStatus.APPROVED)


RETURN_EDGE_HOOK = "Whose boxes carry the fab's spare parts home?"


def llm_with_return_edge():
    llm = well_behaved_llm()

    def plan_with_extra(request):
        from tests.harness.fixture_run import _architect_plan

        payload = json.loads(_architect_plan(request))
        payload["connections"].append(
            {
                "from": "p-chip",
                "to": "p-container",
                "hook_angle": "The fab's tools ride the same boxes back out.",
                "rationale": (
                    "TSMC's spare EUV modules ride home to Rotterdam in the same "
                    "standard boxes that delivered them."
                ),
            }
        )
        return json.dumps(payload)

    def hook_with_extra(request):
        from tests.harness.fixture_run import _hook

        from_id = request.payload["from"]["id"]
        to_id = request.payload["to"]["id"]
        if from_id == "p-chip" and to_id == "p-container":
            return json.dumps(
                {
                    "hook": RETURN_EDGE_HOOK,
                    "rationale": (
                        "TSMC's spare EUV modules ride home to Rotterdam in the same "
                        "standard boxes that delivered them."
                    ),
                }
            )
        return _hook(request)

    llm.on("architect.plan", plan_with_extra)
    llm.on("weaver.hook", hook_with_extra)
    return llm


def test_the_written_graph_after_a_rejection_satisfies_the_outcome_contract(tmp_path):
    ctx = build_context(tmp_path, gates=ScriptedGates(reject={"p-chip"}))
    state = run_pipeline(ctx)
    assert state["status"] == "completed"
    published = sorted(state["published"])
    assert published == ["p-container", "p-money", "p-strait"]
    assert ctx.repo.get_piece("p-chip") is None

    topics = {pid: {t.id for t in ctx.repo.get_piece(pid).topics} for pid in published}
    adjacency = {pid: set() for pid in published}
    for piece_id in published:
        onward = ctx.repo.get_connections_from(piece_id)
        assert onward
        for edge in onward:
            assert edge.to_piece_id in published
            assert topics[edge.to_piece_id] - topics[piece_id]
            adjacency[piece_id].add(edge.to_piece_id)
            adjacency[edge.to_piece_id].add(piece_id)

    seen = {published[0]}
    frontier = [published[0]]
    while frontier:
        for neighbour in adjacency[frontier.pop()]:
            if neighbour not in seen:
                seen.add(neighbour)
                frontier.append(neighbour)
    assert seen == set(published)

    receipt = json.loads(ctx.workspace.read(publish.PUBLISH_RECEIPT))
    assert receipt["pieces"] == published
    assert all(a in published and b in published for a, b in receipt["connections"])


def test_an_unfixable_survivor_is_flagged_back_not_written(tmp_path):
    ctx = build_context(
        tmp_path, llm=llm_with_return_edge(), gates=ScriptedGates(reject={"p-strait"})
    )
    state = run_pipeline(ctx)
    assert state["status"] == "completed"
    assert state["flagged_pieces"] == ["p-money"]
    assert sorted(state["published"]) == ["p-chip", "p-container"]

    flags = ctx.workspace.read(publish.PUBLISH_FLAGS)
    assert "p-money" in flags
    assert ctx.repo.get_piece("p-money") is None
    assert ctx.repo.get_piece("p-strait") is None
    hooks = {edge.hook for edge in ctx.repo.get_connections_from("p-chip")}
    assert hooks == {RETURN_EDGE_HOOK}


def test_publish_dies_loud_when_no_valid_survivor_set_remains(tmp_path):
    ctx = build_context(tmp_path, gates=ScriptedGates(reject={"p-container", "p-chip"}))
    with pytest.raises(PublishIntegrityError, match="flagged back to the human"):
        run_pipeline(ctx)
    assert ctx.repo.list_piece_summaries() == ()
    assert not ctx.workspace.exists(publish.PUBLISH_RECEIPT)


def test_the_constellation_gate_precedes_any_write(tmp_path):
    ctx = build_context(tmp_path, gates=ScriptedGates(pending={"constellation"}))
    state = run_pipeline(ctx)
    assert state["status"] == "paused"
    assert "constellation" in state["detail"]
    assert ctx.workspace.exists(publish.PUBLISH_CONNECTIONS)
    assert ctx.repo.list_piece_summaries() == ()
    assert not ctx.workspace.exists(publish.PUBLISH_RECEIPT)


def test_write_validates_every_survivor_before_any_upsert(tmp_path):
    ctx = build_context(tmp_path)
    stages.run_stage_plan(ctx)
    stages.run_stage_source(ctx)
    stages.run_stage_draft(ctx)
    stages.run_stage_edit(ctx)
    stages.run_stage_wire(ctx)
    stages.run_stage_qa(ctx)
    survivors = frozenset(PIECE_IDS)
    publish.run_stage_rewire(ctx, survivors)
    publish.run_stage_reqa(ctx, survivors)

    ctx.workspace.write(stages.piece_path("p-money"), "this is not a Piece deliverable\n")
    with pytest.raises(PublishIntegrityError, match="pre-write validation"):
        publish.run_stage_write(ctx, survivors)
    assert ctx.repo.list_piece_summaries() == ()
    assert ctx.repo.get_topic("logistics") is None
