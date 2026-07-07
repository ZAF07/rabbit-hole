"""Issue 03 — the Architect designs the constellation; Stage 0 is real."""

import json

import pytest
from tests.harness.fixture_run import FIXTURE_EDGES, FIXTURE_PIECES, build_context

from content_graph.adapters.memory import InMemoryContentGraphRepository
from content_graph.domain.piece import Piece
from content_graph.domain.topic import Topic
from harness.domain.plan import parse_plan
from harness.errors import ContractViolationError
from harness.pipeline import stages
from harness.pipeline.context import HarnessConfig
from harness.pipeline.graph import run_pipeline


def seeded_repo(title: str = "An Older Piece", piece_id: str = "old-1"):
    repo = InMemoryContentGraphRepository()
    repo.upsert_topic(Topic(id="history", slug="history", title="History"))
    repo.upsert_piece(
        Piece(
            id=piece_id,
            title=title,
            teaser="A piece already in the graph.",
            read_time_min=3,
            topic_ids=("history",),
        )
    )
    return repo


def test_plan_deliverable_spans_brief_topics_with_full_skeleton(tmp_path):
    ctx = build_context(tmp_path)
    stages.run_stage_plan(ctx)
    plan = parse_plan(ctx.workspace.read("plan.md"))
    assert len(plan.concepts) == 4
    covered = {topic for concept in plan.concepts for topic in concept.topic_ids}
    assert covered == {"logistics", "semiconductors", "financial-systems", "chokepoints"}
    assert len(plan.connections) == len(FIXTURE_EDGES)
    assert all(edge.hook_angle and edge.rationale for edge in plan.connections)


def test_planned_skeleton_is_structurally_sound_by_construction(tmp_path):
    def dead_end_plan(request):
        payload = json.loads(_fixture_plan_json(request))
        payload["connections"] = [
            edge for edge in payload["connections"] if edge["from"] != "p-strait"
        ]
        return json.dumps(payload)

    ctx = build_context(tmp_path)
    ctx.llm.on("architect.plan", dead_end_plan)
    with pytest.raises(ContractViolationError, match="structurally unsound"):
        stages.run_stage_plan(ctx)
    assert not ctx.workspace.exists("plan.md")


def _fixture_plan_json(request):
    from tests.harness.fixture_run import _architect_plan

    return _architect_plan(request)


def test_architect_re_plans_when_the_first_plan_is_structurally_unsound(tmp_path):
    """A structural failure feeds the violations back and re-plans (issue 08).

    A live model that returns an unsound plan first — here p-strait as a dead
    end (I4) — but corrects once it can see the concrete violations must not
    abort the run: the bounded repair loop re-plans and writes a sound plan.
    """

    def unsound_until_told(request):
        payload = json.loads(_fixture_plan_json(request))
        if request.payload.get("prior_violations"):
            return json.dumps(payload)
        payload["connections"] = [
            edge for edge in payload["connections"] if edge["from"] != "p-strait"
        ]
        return json.dumps(payload)

    ctx = build_context(tmp_path)
    ctx.llm.on("architect.plan", unsound_until_told)
    stages.run_stage_plan(ctx)
    plan = parse_plan(ctx.workspace.read("plan.md"))
    assert len(plan.concepts) == 4
    plan_calls = [r for r in ctx.llm.requests if r.purpose == "architect.plan"]
    assert len(plan_calls) == 2
    assert "structurally unsound" in plan_calls[1].payload["prior_violations"][0]


def test_architect_aborts_when_no_plan_within_the_budget_is_sound(tmp_path):
    """A model that never corrects still aborts after exhausting the budget."""

    def always_dead_end(request):
        payload = json.loads(_fixture_plan_json(request))
        payload["connections"] = [
            edge for edge in payload["connections"] if edge["from"] != "p-strait"
        ]
        return json.dumps(payload)

    ctx = build_context(tmp_path, config=HarnessConfig(plan_repair_budget=2))
    ctx.llm.on("architect.plan", always_dead_end)
    with pytest.raises(ContractViolationError, match="structurally unsound"):
        stages.run_stage_plan(ctx)
    plan_calls = [r for r in ctx.llm.requests if r.purpose == "architect.plan"]
    assert len(plan_calls) == 3
    assert not ctx.workspace.exists("plan.md")


def test_plan_response_contract_states_the_structural_rules(tmp_path):
    ctx = build_context(tmp_path)
    stages.run_stage_plan(ctx)
    request = next(r for r in ctx.llm.requests if r.purpose == "architect.plan")
    assert "no dead ends" in request.instructions
    assert "single connected graph" in request.instructions
    assert "piece_count" in request.instructions


def test_plan_marks_entry_worthy_nodes(tmp_path):
    ctx = build_context(tmp_path)
    stages.run_stage_plan(ctx)
    plan = parse_plan(ctx.workspace.read("plan.md"))
    assert any(concept.entry_worthy for concept in plan.concepts)


def test_plan_without_entry_worthy_node_is_refused(tmp_path):
    def no_entry_plan(request):
        payload = json.loads(_fixture_plan_json(request))
        for concept in payload["concepts"]:
            concept["entry_worthy"] = False
        return json.dumps(payload)

    ctx = build_context(tmp_path)
    ctx.llm.on("architect.plan", no_entry_plan)
    with pytest.raises(ContractViolationError, match="entry-worthy"):
        stages.run_stage_plan(ctx)


def test_architect_reads_the_content_graph_for_dedup(tmp_path):
    ctx = build_context(tmp_path, repo=seeded_repo())
    stages.run_stage_plan(ctx)
    plan_requests = [r for r in ctx.llm.requests if r.purpose == "architect.plan"]
    assert len(plan_requests) == 1
    existing = plan_requests[0].payload["existing_pieces"]
    assert {
        "id": "old-1",
        "title": "An Older Piece",
        "teaser": "A piece already in the graph.",
    } in existing
    plan = parse_plan(ctx.workspace.read("plan.md"))
    assert all(concept.title != "An Older Piece" for concept in plan.concepts)


def test_plan_duplicating_an_existing_piece_is_refused(tmp_path):
    duplicate_title = FIXTURE_PIECES["p-container"]["title"]
    ctx = build_context(tmp_path, repo=seeded_repo(title=duplicate_title))
    with pytest.raises(ContractViolationError, match="duplicates the existing Piece"):
        stages.run_stage_plan(ctx)


def test_placeholder_brief_fails_stage0_before_architect_runs(tmp_path):
    goal = FIXTURE_GOAL_WITH_PLACEHOLDER
    ctx = build_context(tmp_path, goal=goal)
    state = run_pipeline(ctx)
    assert state["status"] == "failed"
    assert "placeholder" in state["detail"]
    assert ctx.llm.requests == []


FIXTURE_GOAL_WITH_PLACEHOLDER = """---
through_line: >
  A perfectly good spine.
target_topics:
  - logistics
  - <Topic>
piece_count: 4
---
"""


def test_architect_prompt_carries_the_markdown_specs(tmp_path):
    ctx = build_context(tmp_path)
    stages.run_stage_plan(ctx)
    request = next(r for r in ctx.llm.requests if r.purpose == "architect.plan")
    assert "Editorial DNA" in request.instructions
    assert "Connection & hook checks" in request.instructions
    assert "Constellation-level checks" in request.instructions
    assert "taxonomy" in request.instructions.lower()


def _schema_faithful_plan(request):
    """A model that emits the decoder's keys only if the prompt names them.

    Reproduces issue 07: given the fixture's content but told nothing about the
    wire schema, a schema-blind model picks plausible-but-wrong top-level keys
    (`pieces`/`edges`), and ``decode_plan`` fails. Told the contract, it emits
    ``concepts``/``connections`` and the stage succeeds.
    """
    concepts = json.loads(_fixture_plan_json(request))["concepts"]
    edges = json.loads(_fixture_plan_json(request))["connections"]
    instructions = request.instructions.lower()
    if "concepts" in instructions and "connections" in instructions:
        return json.dumps({"concepts": concepts, "connections": edges})
    return json.dumps({"pieces": concepts, "edges": edges})


def test_architect_prompt_states_the_plan_response_contract(tmp_path):
    ctx = build_context(tmp_path)
    ctx.llm.on("architect.plan", _schema_faithful_plan)
    stages.run_stage_plan(ctx)
    plan = parse_plan(ctx.workspace.read("plan.md"))
    assert len(plan.concepts) == 4
    assert len(plan.connections) == len(FIXTURE_EDGES)
