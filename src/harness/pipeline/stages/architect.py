"""The Architect — Stage 0 gate and Stage 1 plan.

Designs the whole constellation graph before any prose (plan-first, ADR 0003),
and refuses the run up front if the Editorial DNA or a placeholder-free Theme
Brief is missing. Downstream stages fill a graph whose shape is already fixed.
"""

from collections.abc import Sequence

from content_graph.domain.read_models import PieceSummary
from harness.domain.artifacts import ConstellationArtifact, PieceArtifact, WiredConnection
from harness.domain.brief import ThemeBrief, find_placeholders, parse_brief
from harness.domain.plan import ConstellationPlan, render_plan
from harness.errors import ContractViolationError
from harness.guardrails.constellation import evaluate_constellation
from harness.pipeline.context import RunContext
from harness.pipeline.decode import decode_plan
from harness.pipeline.stages._kernel import GOAL, PLAN, load_brief
from harness.ports.llm import LLMRequest


def run_stage_gate0(ctx: RunContext) -> str | None:
    """Stage 0 — refuse to start unless DNA + a placeholder-free Brief exist.

    Args:
        ctx: The run context.

    Returns:
        None if the gate passes, otherwise the concrete failure reason.
    """
    try:
        dna = ctx.specs.dna_text()
    except OSError:
        return "Editorial DNA (harness/editorial/dna.md) is missing"
    if not dna.strip():
        return "Editorial DNA is empty"
    if not ctx.workspace.exists(GOAL):
        return "Theme Brief (goal.md) is missing from the run workspace"
    raw = ctx.workspace.read(GOAL)
    placeholders = find_placeholders(raw)
    if placeholders:
        return f"Theme Brief has unfilled placeholders: {', '.join(placeholders)}"
    try:
        parse_brief(raw)
    except Exception as error:  # noqa: BLE001
        return f"Theme Brief is invalid: {error}"
    return None


def run_stage_plan(ctx: RunContext) -> None:
    """Stage 1 — the Architect designs the whole constellation before any prose.

    Args:
        ctx: The run context.
    """
    stage = ctx.manifest.stage("plan")
    ctx.workspace.require(stage.name, *stage.prerequisites)
    if ctx.workspace.exists(PLAN):
        return
    brief = load_brief(ctx)
    existing = ctx.repo.list_piece_summaries()
    request = LLMRequest(
        purpose="architect.plan",
        instructions="\n\n---\n\n".join(
            (
                ctx.specs.dna_text(),
                ctx.specs.guardrail_text("connection"),
                ctx.specs.guardrail_text("constellation"),
                ctx.specs.taxonomy_text(),
            )
        ),
        payload={
            "through_line": brief.through_line,
            "target_topics": list(brief.target_topics),
            "piece_count": list(brief.piece_count),
            "must_include": list(brief.must_include),
            "entry_hints": list(brief.entry_hints),
            "must_avoid": list(brief.must_avoid),
            "notes": brief.notes,
            "existing_pieces": [
                {"id": summary.id, "title": summary.title, "teaser": summary.teaser}
                for summary in existing
            ],
        },
    )
    plan = decode_plan(ctx.llm.complete(request))
    _assert_no_duplicates(plan, existing)
    _assert_plan_sound(plan, brief)
    ctx.workspace.write(PLAN, render_plan(plan))


def _assert_no_duplicates(plan: ConstellationPlan, existing: Sequence[PieceSummary]) -> None:
    """Refuse a plan that duplicates a Piece already in the Content Graph.

    The Architect reads the published graph to bridge to it, not to
    re-plan it; the LLM is instructed to avoid duplicates and this backstop
    makes the guarantee hard.

    Args:
        plan: The proposed plan.
        existing: The published Pieces the Architect was shown.

    Raises:
        ContractViolationError: If a proposed concept collides with an
            existing Piece by id or normalized title.
    """
    existing_ids = {summary.id for summary in existing}
    existing_titles = {summary.title.strip().casefold() for summary in existing}
    for concept in plan.concepts:
        if concept.id in existing_ids:
            raise ContractViolationError(
                f"plan proposes Piece id {concept.id!r} which already exists in the Content Graph"
            )
        if concept.title.strip().casefold() in existing_titles:
            raise ContractViolationError(
                f"plan duplicates the existing Piece titled {concept.title!r}"
            )


def _assert_plan_sound(plan: ConstellationPlan, brief: ThemeBrief) -> None:
    """Check the plan's structural invariants hold by construction.

    Args:
        plan: The proposed plan.
        brief: The run's Brief.

    Raises:
        ContractViolationError: If the planned skeleton could not satisfy
            the outcome contract (dead ends, missing cross-Topic edges,
            disconnection, count/coverage misses, or duplicate ids).
    """
    ids = [concept.id for concept in plan.concepts]
    if len(set(ids)) != len(ids):
        raise ContractViolationError("plan proposes duplicate Piece ids")
    planned = ConstellationArtifact(
        pieces=tuple(
            PieceArtifact(
                id=concept.id,
                title=concept.title,
                teaser=concept.premise or concept.title,
                read_time_min=5,
                topic_ids=concept.topic_ids,
            )
            for concept in plan.concepts
        ),
        connections=tuple(
            WiredConnection(
                from_piece_id=edge.from_piece_id,
                to_piece_id=edge.to_piece_id,
                hook=edge.hook_angle,
                rationale=edge.rationale,
            )
            for edge in plan.connections
        ),
        piece_count_target=brief.piece_count,
        target_topic_ids=brief.target_topics,
    )
    report = evaluate_constellation(planned, banned_phrases=())
    structural = [
        violation
        for violation in report.violations
        if violation.code in {"I1", "I3", "I4", "I5", "I6", "I7"}
        and "guardrails" not in violation.message
    ]
    if structural:
        summary = "; ".join(f"{v.code} {v.subject}: {v.message}" for v in structural[:5])
        raise ContractViolationError(f"planned skeleton is structurally unsound: {summary}")
    if not any(concept.entry_worthy for concept in plan.concepts):
        raise ContractViolationError("plan marks no entry-worthy node (J3)")
