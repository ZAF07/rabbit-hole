"""Issue 05 — Writer (closed-book blocks) + Editor (machine-QA loop, 4.5 check)."""

import dataclasses
import json
import shutil

import pytest
from tests.harness.fixture_run import FIXTURE_PIECES, REPO_ROOT, build_context

from content_graph.domain.blocks import BlockKind
from harness.domain.piece_io import parse_piece
from harness.errors import GroundingDriftError, QABudgetExceededError
from harness.pipeline import stages
from harness.specs import SpecLibrary

PLANTED = "McLean also secretly invented the barcode in 1949."


def run_through_edit(ctx):
    stages.run_stage_plan(ctx)
    stages.run_stage_source(ctx)
    stages.run_stage_draft(ctx)
    stages.run_stage_edit(ctx)


def test_writer_drafts_only_from_the_claim_pack(tmp_path):
    ctx = build_context(tmp_path)
    stages.run_stage_plan(ctx)
    stages.run_stage_source(ctx)
    stages.run_stage_draft(ctx)
    request = next(r for r in ctx.llm.requests if r.purpose == "writer.draft")
    claim_ids = {claim["id"] for claim in request.payload["claims"]}
    piece_id = str(request.payload["piece_id"])
    expected = {claim["id"] for claim in FIXTURE_PIECES[piece_id]["claims"]}
    assert claim_ids == expected
    assert "premise" in request.payload


def test_writer_emits_well_formed_ordered_blocks(tmp_path):
    ctx = build_context(tmp_path)
    data = FIXTURE_PIECES["p-container"]

    def structured_draft(request):
        if str(request.payload["piece_id"]) != "p-container":
            from tests.harness.fixture_run import _draft

            return _draft(request)
        return json.dumps(
            {
                "title": data["title"],
                "teaser": data["teaser"],
                "read_time_min": 4,
                "blocks": [
                    {"kind": "paragraph", "text": data["paragraphs"][0]},
                    {"kind": "heading", "text": "The Arithmetic", "level": 2},
                    {"kind": "paragraph", "text": data["paragraphs"][1]},
                    {
                        "kind": "pull-quote",
                        "text": "We were just trying to save money on trucks.",
                        "attribution": "Malcom McLean",
                    },
                    {"kind": "stat-callout", "value": "58", "label": "containers on the Ideal-X"},
                    {"kind": "paragraph", "text": data["paragraphs"][2]},
                ],
            }
        )

    ctx.llm.on("writer.draft", structured_draft)
    ctx.llm.on("editor.revise", structured_draft)
    ctx.llm.on("editor.cut", structured_draft)
    run_through_edit(ctx)
    artifact = parse_piece(ctx.workspace.read(stages.piece_path("p-container")))
    assert [block.kind for block in artifact.blocks] == [
        BlockKind.PARAGRAPH,
        BlockKind.HEADING,
        BlockKind.PARAGRAPH,
        BlockKind.PULL_QUOTE,
        BlockKind.STAT_CALLOUT,
        BlockKind.PARAGRAPH,
    ]
    quote = artifact.blocks[3]
    assert quote.payload["attribution"] == "Malcom McLean"


def test_planted_out_of_pack_fact_is_cut_not_carried_through(tmp_path):
    ctx = build_context(tmp_path)

    def draft_with_drift(request):
        from tests.harness.fixture_run import _draft

        payload = json.loads(_draft(request))
        if str(request.payload["piece_id"]) == "p-container":
            payload["blocks"].insert(
                1, {"kind": "paragraph", "text": f"{PLANTED} Nobody checked in 1949."}
            )
        return json.dumps(payload)

    def ground(request):
        if PLANTED in str(request.payload["text"]):
            return json.dumps({"unsupported": [{"text": PLANTED}]})
        return json.dumps({"unsupported": []})

    def cut(request):
        blocks = [
            block
            for block in request.payload["blocks"]
            if PLANTED not in str(block.get("text", ""))
        ]
        return json.dumps(
            {
                "title": request.payload["title"],
                "teaser": request.payload["teaser"],
                "read_time_min": request.payload["read_time_min"],
                "blocks": blocks,
            }
        )

    ctx.llm.on("writer.draft", draft_with_drift)
    ctx.llm.on("editor.ground", ground)
    ctx.llm.on("editor.cut", cut)
    run_through_edit(ctx)
    final = ctx.workspace.read(stages.piece_path("p-container"))
    assert PLANTED not in final
    assert any(r.purpose == "editor.cut" for r in ctx.llm.requests)


def test_unresolvable_drift_fails_loud(tmp_path):
    ctx = build_context(tmp_path)
    ctx.llm.on("editor.ground", lambda r: json.dumps({"unsupported": [{"text": "ghost fact"}]}))
    with pytest.raises(GroundingDriftError, match="unsupported assertions"):
        run_through_edit(ctx)


def test_editor_loops_until_the_piece_evaluator_passes(tmp_path):
    ctx = build_context(tmp_path)

    def sloppy_draft(request):
        from tests.harness.fixture_run import _draft

        payload = json.loads(_draft(request))
        if str(request.payload["piece_id"]) == "p-container":
            payload["blocks"][1]["text"] += " This proved to be a game-changer for the industry."
        return json.dumps(payload)

    ctx.llm.on("writer.draft", sloppy_draft)
    run_through_edit(ctx)
    final = ctx.workspace.read(stages.piece_path("p-container"))
    assert "game-changer" not in final
    assert any(r.purpose == "editor.revise" for r in ctx.llm.requests)


def test_unfixable_piece_is_escalated_never_silently_shipped(tmp_path):
    ctx = build_context(tmp_path)

    def always_sloppy(request):
        from tests.harness.fixture_run import _draft

        payload = json.loads(_draft(request))
        payload["blocks"][1]["text"] += " This proved to be a game-changer for the industry."
        return json.dumps(payload)

    ctx.llm.on("writer.draft", always_sloppy)
    ctx.llm.on("editor.revise", always_sloppy)
    with pytest.raises(QABudgetExceededError, match="escalating to the human queue"):
        run_through_edit(ctx)
    assert not ctx.workspace.exists(stages.piece_path("p-container"))


def test_judged_violations_also_drive_the_loop(tmp_path):
    ctx = build_context(tmp_path)
    calls = {"n": 0}

    def judge_once(request):
        calls["n"] += 1
        if calls["n"] == 1:
            return json.dumps(
                {
                    "violations": [
                        {"code": "C1", "message": "no reframe — flat summary of known facts"}
                    ]
                }
            )
        return json.dumps({"violations": []})

    ctx.llm.on("editor.judge", judge_once)
    run_through_edit(ctx)
    revise_requests = [r for r in ctx.llm.requests if r.purpose == "editor.revise"]
    assert revise_requests
    codes = [v["code"] for v in revise_requests[0].payload["violations"]]
    assert "C1" in codes


def test_voice_profile_swap_is_a_file_change_not_a_code_change(tmp_path):
    specs_root = tmp_path / "specs-root"
    shutil.copytree(REPO_ROOT / "harness", specs_root / "harness")
    (specs_root / "docs").mkdir()
    shutil.copy(REPO_ROOT / "docs" / "taxonomy.md", specs_root / "docs" / "taxonomy.md")
    guest_voice = specs_root / "harness" / "editorial" / "voices" / "guest-columnist.md"
    guest_voice.write_text(
        "# Voice Profile — Guest Columnist\n\nFirst person, wry, exactly one aside per piece.\n"
    )
    from tests.harness.fixture_run import FIXTURE_GOAL

    goal_with_voice = FIXTURE_GOAL.replace(
        "piece_count: 4", "piece_count: 4\nvoice: guest-columnist"
    )
    ctx = build_context(tmp_path, goal=goal_with_voice)
    ctx = dataclasses.replace(ctx, specs=SpecLibrary(repo_root=specs_root))
    stages.run_stage_plan(ctx)
    stages.run_stage_source(ctx)
    stages.run_stage_draft(ctx)
    request = next(r for r in ctx.llm.requests if r.purpose == "writer.draft")
    assert "Guest Columnist" in request.instructions
    assert "exactly one aside per piece" in request.instructions


def test_writer_never_sees_dropped_or_flagged_claims(tmp_path):
    ctx = build_context(tmp_path)

    def harvest_with_internal(request):
        from tests.harness.fixture_run import _harvest

        payload = json.loads(_harvest(request))
        payload["claims"].append(
            {
                "id": f"{request.payload['piece_id']}-c9",
                "text": "An unsourced memory.",
                "load_bearing": False,
                "candidate_urls": [],
            }
        )
        return json.dumps(payload)

    ctx.llm.on("researcher.harvest", harvest_with_internal)
    stages.run_stage_plan(ctx)
    stages.run_stage_source(ctx)
    stages.run_stage_draft(ctx)
    request = next(r for r in ctx.llm.requests if r.purpose == "writer.draft")
    claim_ids = {claim["id"] for claim in request.payload["claims"]}
    assert not any(claim_id.endswith("-c9") for claim_id in claim_ids)
