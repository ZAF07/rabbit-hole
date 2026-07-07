"""The Weaver — Stage 5, realizing every planned Connection with a passing hook.

Also serves the post-approval re-wire mode (ADR 0012) when ``survivors``
restricts the Piece set — the publish gate calls it with the approved subset.
"""

from harness.domain.artifacts import WiredConnection
from harness.domain.plan import PieceConcept, PlannedConnection
from harness.domain.wiring import render_connections
from harness.errors import QABudgetExceededError
from harness.guardrails.connection import evaluate_connections
from harness.pipeline.context import RunContext
from harness.pipeline.decode import decode_object
from harness.pipeline.stages._kernel import (
    CONNECTIONS,
    expanded_prerequisites,
    load_brief,
    load_plan,
    voice_name,
)
from harness.ports.llm import LLMRequest


def run_stage_wire(
    ctx: RunContext, output_path: str = CONNECTIONS, survivors: frozenset[str] | None = None
) -> None:
    """Stage 5 — the Weaver realizes every planned Connection with a passing hook.

    Also serves as the post-approval re-wire mode (ADR 0012) when
    ``survivors`` restricts the Piece set.

    Args:
        ctx: The run context.
        output_path: Where to write the wired Connections.
        survivors: When re-wiring, the approved Piece ids; None wires the
            full plan.

    Raises:
        QABudgetExceededError: If a hook cannot pass within the hook budget.
    """
    stage = ctx.manifest.stage("wire" if survivors is None else "rewire")
    plan = load_plan(ctx)
    concept_ids = [
        concept.id for concept in plan.concepts if survivors is None or concept.id in survivors
    ]
    ctx.workspace.require(stage.name, *expanded_prerequisites(stage, concept_ids))
    if ctx.workspace.exists(output_path):
        return
    brief = load_brief(ctx)
    voice = ctx.specs.voice_text(voice_name(ctx, brief))
    connection_spec = ctx.specs.guardrail_text("connection")
    banned = ctx.specs.banned_phrases()
    concepts = {concept.id: concept for concept in plan.concepts}
    keep = frozenset(concept_ids)
    edges: list[WiredConnection] = []
    for planned in plan.connections:
        if planned.from_piece_id not in keep or planned.to_piece_id not in keep:
            continue
        edges.append(_realize_hook(ctx, planned, concepts, edges, voice, connection_spec, banned))
    ctx.workspace.write(output_path, render_connections(tuple(edges)))


def _realize_hook(
    ctx: RunContext,
    planned: PlannedConnection,
    concepts: dict[str, PieceConcept],
    existing: list[WiredConnection],
    voice: str,
    connection_spec: str,
    banned: tuple[str, ...],
) -> WiredConnection:
    """Write one Connection's per-origin hook, retrying failed hooks.

    Args:
        ctx: The run context.
        planned: The planned edge (from plan.md).
        concepts: Concept lookup by id.
        existing: Edges already realized (for the set-level B3 check).
        voice: The active Voice Profile text.
        connection_spec: The connection guardrail text.
        banned: The banned-filler list.

    Returns:
        A wired Connection that passes the connection guardrails.

    Raises:
        QABudgetExceededError: If the hook budget is spent without a pass.
    """
    feedback: list[dict[str, object]] = []
    for _ in range(ctx.config.hook_budget + 1):
        response = decode_object(
            ctx.llm.complete(
                LLMRequest(
                    purpose="weaver.hook",
                    instructions=f"{connection_spec}\n\n---\n\n{voice}",
                    payload={
                        "from": {
                            "id": planned.from_piece_id,
                            "title": concepts[planned.from_piece_id].title,
                            "premise": concepts[planned.from_piece_id].premise,
                        },
                        "to": {
                            "id": planned.to_piece_id,
                            "title": concepts[planned.to_piece_id].title,
                            "premise": concepts[planned.to_piece_id].premise,
                        },
                        "hook_angle": planned.hook_angle,
                        "rationale": planned.rationale,
                        "violations": feedback,
                    },
                )
            ),
            purpose="weaver.hook",
        )
        candidate = WiredConnection(
            from_piece_id=planned.from_piece_id,
            to_piece_id=planned.to_piece_id,
            hook=str(response.get("hook", "")),
            rationale=str(response.get("rationale", planned.rationale)),
        )
        violations = [
            violation
            for violation in evaluate_connections((*existing, candidate), banned)
            if violation.subject in (candidate.subject(), f"->{candidate.to_piece_id}")
        ]
        if not violations:
            return candidate
        feedback = [{"code": v.code, "message": v.message} for v in violations]
    raise QABudgetExceededError(
        f"hook for {planned.from_piece_id}->{planned.to_piece_id} failed the connection "
        f"guardrails {ctx.config.hook_budget + 1} time(s): "
        + "; ".join(str(item["message"]) for item in feedback)
    )
