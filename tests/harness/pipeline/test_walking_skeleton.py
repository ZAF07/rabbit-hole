"""Issue 02 — the gated StateGraph runs end-to-end on the fixture Brief."""

import dataclasses

import pytest
from tests.harness.fixture_run import PIECE_IDS, REPO_ROOT, build_context

from harness.domain.artifacts import ConstellationArtifact, PieceArtifact, WiredConnection
from harness.domain.grounding_io import ledger_from_json
from harness.errors import MissingPrerequisiteError
from harness.guardrails.constellation import evaluate_constellation
from harness.pipeline import stages
from harness.pipeline.graph import run_pipeline


def test_end_to_end_run_completes(tmp_path):
    ctx = build_context(tmp_path)
    state = run_pipeline(ctx)
    assert state["status"] == "completed"
    assert sorted(state["published"]) == sorted(PIECE_IDS)


def test_written_constellation_passes_tier1_contract(tmp_path, banned_phrases):
    ctx = build_context(tmp_path)
    run_pipeline(ctx)

    summaries = ctx.repo.list_piece_summaries()
    pieces = []
    connections = []
    for summary in summaries:
        read = ctx.repo.get_piece(summary.id)
        assert read is not None
        pieces.append(
            PieceArtifact(
                id=read.id,
                title=read.title,
                teaser=read.teaser,
                read_time_min=read.read_time_min,
                topic_ids=tuple(topic.id for topic in read.topics),
                blocks=tuple(read.blocks),
            )
        )
        connections.extend(
            WiredConnection(
                from_piece_id=preview.from_piece_id,
                to_piece_id=preview.to_piece_id,
                hook=preview.hook,
                rationale="written edge",
            )
            for preview in ctx.repo.get_connections_from(summary.id)
        )
    ledgers = {
        piece_id: ledger_from_json(ctx.workspace.read(stages.grounding_path(piece_id)))
        for piece_id in PIECE_IDS
    }
    constellation = ConstellationArtifact(
        pieces=tuple(pieces),
        connections=tuple(connections),
        ledgers=ledgers,
        piece_count_target=(4, 4),
        target_topic_ids=("logistics", "semiconductors", "financial-systems", "chokepoints"),
    )
    report = evaluate_constellation(constellation, banned_phrases)
    assert report.passed, report.violations


def test_run_workspace_has_every_deliverable(tmp_path):
    ctx = build_context(tmp_path)
    run_pipeline(ctx)
    for relative in ("plan.md", "connections.md", "qa.md", "publish/published.json"):
        assert ctx.workspace.exists(relative), relative
    for piece_id in PIECE_IDS:
        for template in (
            "pieces/{pid}/sources.md",
            "pieces/{pid}/grounding.json",
            "pieces/{pid}/draft.md",
            "pieces/{pid}/piece.md",
        ):
            assert ctx.workspace.exists(template.format(pid=piece_id)), (piece_id, template)


def test_stage_refuses_to_start_without_prerequisite(tmp_path):
    ctx = build_context(tmp_path)
    with pytest.raises(MissingPrerequisiteError):
        stages.run_stage_source(ctx)


def test_draft_refuses_without_claim_pack(tmp_path):
    ctx = build_context(tmp_path)
    stages.run_stage_plan(ctx)
    with pytest.raises(MissingPrerequisiteError):
        stages.run_stage_draft(ctx)


def test_wire_refuses_without_final_pieces(tmp_path):
    ctx = build_context(tmp_path)
    stages.run_stage_plan(ctx)
    with pytest.raises(MissingPrerequisiteError):
        stages.run_stage_wire(ctx)


def test_stage0_short_circuits_on_placeholder_brief(tmp_path):
    goal = "---\nthrough_line: >\n  <fill this in>\ntarget_topics:\n  - a\npiece_count: 4\n---\n"
    ctx = build_context(tmp_path, goal=goal)
    state = run_pipeline(ctx)
    assert state["status"] == "failed"
    assert "placeholder" in state["detail"]
    assert not ctx.workspace.exists("plan.md")


def test_stage0_short_circuits_on_missing_brief(tmp_path):
    ctx = build_context(tmp_path, goal="")
    state = run_pipeline(ctx)
    assert state["status"] == "failed"
    assert "goal.md" in state["detail"]


def test_stage0_short_circuits_on_missing_or_empty_dna(tmp_path):
    import shutil

    from harness.specs import SpecLibrary

    specs_root = tmp_path / "specs-root"
    shutil.copytree(REPO_ROOT / "harness", specs_root / "harness")
    (specs_root / "docs").mkdir()
    shutil.copy(REPO_ROOT / "docs" / "taxonomy.md", specs_root / "docs" / "taxonomy.md")
    dna = specs_root / "harness" / "editorial" / "dna.md"

    dna.write_text("   \n")
    ctx = build_context(tmp_path)
    ctx = dataclasses.replace(ctx, specs=SpecLibrary(repo_root=specs_root))
    state = run_pipeline(ctx)
    assert state["status"] == "failed"
    assert "DNA is empty" in state["detail"]

    dna.unlink()
    state = run_pipeline(ctx)
    assert state["status"] == "failed"
    assert "DNA" in state["detail"] and "missing" in state["detail"]
    assert not ctx.workspace.exists("plan.md")


def test_boundary_only_pieces_connections_topics_cross(tmp_path):
    ctx = build_context(tmp_path)
    run_pipeline(ctx)
    read = ctx.repo.get_piece("p-container")
    assert read is not None
    assert {field.name for field in dataclasses.fields(read)} == {
        "id",
        "title",
        "teaser",
        "read_time_min",
        "blocks",
        "topics",
    }
    preview = ctx.repo.get_connections_from("p-container")[0]
    assert {field.name for field in dataclasses.fields(preview)} == {
        "from_piece_id",
        "to_piece_id",
        "hook",
        "to_title",
        "to_topics",
    }
    summary_fields = {
        field.name for field in dataclasses.fields(ctx.repo.list_piece_summaries()[0])
    }
    assert "run_id" not in summary_fields
    assert "grounding" not in str(summary_fields)


def test_manifest_is_data_with_fixed_stage_order(tmp_path):
    ctx = build_context(tmp_path)
    names = [stage.name for stage in ctx.manifest.stages]
    assert names == [
        "gate",
        "plan",
        "source",
        "draft",
        "edit",
        "wire",
        "qa",
        "rewire",
        "reqa",
        "write",
    ]
    agents = [stage.agent for stage in ctx.manifest.stages[:7]]
    assert agents == ["", "architect", "researcher", "writer", "editor", "weaver", "reviewer"]
    assert [gate.name for gate in ctx.manifest.human_gates] == ["plan", "piece", "constellation"]


def test_rerun_resumes_idempotently(tmp_path):
    ctx = build_context(tmp_path)
    first = run_pipeline(ctx)
    calls_after_first = len(ctx.llm.requests)
    second = run_pipeline(ctx)
    assert first["status"] == second["status"] == "completed"
    assert len(ctx.llm.requests) == calls_after_first
