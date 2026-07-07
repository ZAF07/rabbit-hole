"""The Editor — Stage 4, anti-slop pass, machine-QA loop, 4.5 grounding check.

A bounded agent revises the draft against a deterministic ``check_guardrails``
tool; the deterministic ``evaluate_piece`` stays the arbiter after the agent
finishes; then every assertion is mapped back to a verified claim and drift is
cut. A Piece that fails its bar is persisted as a best-effort machine copy plus
a failure marker and routed into the piece gate (ADR 0016 Decision 7).
"""

import json
from collections.abc import Mapping
from dataclasses import dataclass

from harness.domain.artifacts import PieceArtifact
from harness.domain.grounding_io import ledger_from_json
from harness.domain.piece_io import parse_piece, render_piece
from harness.domain.plan import PieceConcept
from harness.errors import GroundingDriftError, QABudgetExceededError
from harness.guardrails.piece import JUDGED_PIECE_CHECKS, evaluate_piece
from harness.guardrails.violations import Violation
from harness.pipeline.context import RunContext
from harness.pipeline.decode import decode_object_list, decode_piece_payload
from harness.pipeline.stages._kernel import (
    _fan_out,
    _record_failure,
    draft_path,
    grounding_path,
    load_brief,
    load_plan,
    piece_path,
    voice_name,
)
from harness.ports.llm import LLMRequest, ToolSpec


def run_stage_edit(ctx: RunContext) -> None:
    """Stage 4 — the Editor: anti-slop pass, machine-QA loop, 4.5 grounding check.

    The machine-QA judge combines the mechanical piece evaluator with the
    LLM-judged checks and loops the edit until pass or the QA budget is
    spent; then every factual assertion is mapped back to a verified claim.

    A Piece that fails its bar (the machine-QA loop or the 4.5 grounding
    check) no longer aborts the run: the stage finishes every other Piece,
    persists the Piece's best-effort machine copy (its draft) as ``piece.md``
    plus a failure marker (its failure code), and lets it flow into the piece
    gate as an ordinary review target — the human's edit-approve fix (or a
    rejection) is the same path any Verdict takes.

    Args:
        ctx: The run context.
    """
    stage = ctx.manifest.stage("edit")
    brief = load_brief(ctx)
    plan = load_plan(ctx)
    banned = ctx.specs.banned_phrases()
    voice = ctx.specs.voice_text(voice_name(ctx, brief))
    piece_spec = ctx.specs.guardrail_text("piece")

    def work(concept: PieceConcept) -> None:
        if ctx.workspace.exists(piece_path(concept.id)):
            return
        ctx.workspace.require(
            stage.name, *(stage.expand(path, concept.id) for path in stage.prerequisites)
        )
        draft = parse_piece(ctx.workspace.read(draft_path(concept.id)))
        result = _qa_loop(ctx, draft, banned, voice, piece_spec)
        if result.failure_code is None:
            result = _grounding_check(ctx, concept, result.artifact, banned)
        if result.failure_code is None:
            ctx.workspace.write(piece_path(concept.id), render_piece(result.artifact))
        else:
            ctx.workspace.write(piece_path(concept.id), render_piece(draft))
            _record_failure(ctx, concept.id, result.failure_code, result.detail)

    _fan_out(ctx, plan.concepts, work)


def _judge(
    ctx: RunContext, artifact: PieceArtifact, voice: str, piece_spec: str
) -> list[Violation]:
    """Ask the LLM judge for the non-mechanical piece checks.

    Args:
        ctx: The run context.
        artifact: The Piece under judgment.
        voice: The active Voice Profile text.
        piece_spec: The piece guardrail text.

    Returns:
        The judged violations.
    """
    judged = decode_object_list(
        ctx.llm.complete(
            LLMRequest(
                purpose="editor.judge",
                instructions=f"{piece_spec}\n\n---\n\n{voice}",
                payload={
                    "piece_id": artifact.id,
                    "text": artifact.all_text(),
                    "checks": dict(JUDGED_PIECE_CHECKS),
                },
            )
        ),
        key="violations",
        purpose="editor.judge",
    )
    return [
        Violation(
            code=str(item.get("code", "F1")),
            subject=artifact.id,
            message=str(item.get("message", "")),
            excerpt=str(item["excerpt"]) if item.get("excerpt") else None,
        )
        for item in judged
    ]


def _check_guardrails_tool(
    ctx: RunContext,
    piece_id: str,
    topic_ids: tuple[str, ...],
    banned: tuple[str, ...],
    voice: str,
    piece_spec: str,
) -> ToolSpec:
    """Build the Editor's ``check_guardrails`` tool: evaluate + judge a candidate.

    The tool wraps the deterministic ``evaluate_piece`` **and** the
    non-mechanical LLM voice judge, so the agent sees the checker's verdict
    and revises again within one loop. The judge call carries the authored
    ``piece_spec + voice`` — it is never reduced to voice-blind codes.

    Args:
        ctx: The run context.
        piece_id: The Piece id (candidates cannot rename it).
        topic_ids: The Piece's Topic tags.
        banned: The banned-filler list.
        voice: The active Voice Profile text.
        piece_spec: The piece guardrail text.

    Returns:
        The tool the Editor agent calls to check a revision.
    """
    schema = {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "teaser": {"type": "string"},
            "read_time_min": {"type": "integer"},
            "blocks": {"type": "array", "items": {"type": "object"}},
        },
        "required": ["blocks"],
    }

    def run(args: Mapping[str, object]) -> str:
        candidate = decode_piece_payload(json.dumps(dict(args)), piece_id, topic_ids, "editor.qa")
        violations = list(evaluate_piece(candidate, banned)) + _judge(
            ctx, candidate, voice, piece_spec
        )
        return json.dumps(
            {
                "violations": [
                    {"code": v.code, "message": v.message, "excerpt": v.excerpt} for v in violations
                ]
            }
        )

    return ToolSpec(
        name="check_guardrails",
        description=(
            "Evaluate the current draft against the piece guardrails and the "
            "voice judge. Pass the candidate's title, teaser, read_time_min, "
            "and blocks; returns the list of remaining violations (empty when "
            "the draft passes)."
        ),
        parameters=schema,
        run=run,
    )


@dataclass(frozen=True)
class _EditResult:
    """The outcome of one Piece's edit — its artifact and any bar failure.

    Attributes:
        artifact: The best-effort artifact (the agent's output / cut result),
            persisted as ``piece.md`` whether or not it passed.
        failure_code: The failure code when a bar was not met, else None.
        detail: The failure detail (the violations / drift summary).
    """

    artifact: PieceArtifact
    failure_code: str | None
    detail: str


def _qa_loop(
    ctx: RunContext,
    artifact: PieceArtifact,
    banned: tuple[str, ...],
    voice: str,
    piece_spec: str,
) -> _EditResult:
    """Revise the draft via a bounded agent over ``check_guardrails``.

    The Editor agent loops draft → check → revise within one ``run_agent``
    call (bounded by ``agent_step_limit``), carrying the authored
    ``piece_spec + voice`` as its system prompt. The deterministic
    ``evaluate_piece`` — not the model's self-assessment — is the arbiter
    *after* the agent finishes; a Piece that still fails is reported as a
    ``QABudgetExceededError`` bar failure (collected, not raised) so the
    stage can route it to the human queue.

    Args:
        ctx: The run context.
        artifact: The draft artifact.
        banned: The banned-filler list.
        voice: The active Voice Profile text.
        piece_spec: The piece guardrail text.

    Returns:
        The edit result — the revised artifact and any bar failure.
    """
    topic_ids = tuple(artifact.topic_ids)
    tool = _check_guardrails_tool(ctx, artifact.id, topic_ids, banned, voice, piece_spec)
    revised = decode_piece_payload(
        ctx.llm.run_agent(
            LLMRequest(
                purpose="editor.qa",
                instructions=f"{piece_spec}\n\n---\n\n{voice}",
                payload={
                    "piece_id": artifact.id,
                    "title": artifact.title,
                    "teaser": artifact.teaser,
                    "read_time_min": artifact.read_time_min,
                    "blocks": _blocks_payload(artifact),
                },
            ),
            [tool],
            step_limit=ctx.config.agent_step_limit,
        ),
        piece_id=artifact.id,
        topic_ids=topic_ids,
        purpose="editor.qa",
    )
    residual = evaluate_piece(revised, banned)
    if residual:
        summary = "; ".join(f"{v.code}: {v.message}" for v in residual[:5])
        return _EditResult(
            revised,
            QABudgetExceededError.__name__,
            f"Piece {artifact.id!r} still fails after the agentic QA loop "
            f"(step_limit={ctx.config.agent_step_limit}): {summary}",
        )
    return _EditResult(revised, None, "")


def _blocks_payload(artifact: PieceArtifact) -> list[dict[str, object]]:
    """Represent an artifact's blocks as JSON-ready dicts.

    Args:
        artifact: The Piece.

    Returns:
        One dict per block, carrying kind + payload fields.
    """
    return [{"kind": str(block.kind), **dict(block.payload)} for block in artifact.blocks]


def _grounding_check(
    ctx: RunContext,
    concept: PieceConcept,
    artifact: PieceArtifact,
    banned: tuple[str, ...],
) -> _EditResult:
    """Stage 4.5 — map every assertion back to a verified claim; cut drift.

    Args:
        ctx: The run context.
        concept: The planned Piece.
        artifact: The edited artifact.
        banned: The banned-filler list (final re-check after a cut).

    Returns:
        The edit result — the grounded artifact and any bar failure
        (``GroundingDriftError`` if drift survives, ``QABudgetExceededError``
        if the cut re-broke the guardrails).
    """
    ledger = ledger_from_json(ctx.workspace.read(grounding_path(concept.id)))
    claims = [{"id": claim.id, "text": claim.text} for claim in ledger.verified_claims()]
    for attempt in range(2):
        unsupported = decode_object_list(
            ctx.llm.complete(
                LLMRequest(
                    purpose="editor.ground",
                    instructions=ctx.specs.guardrail_text("sourcing"),
                    payload={
                        "piece_id": artifact.id,
                        "text": artifact.all_text(),
                        "claims": claims,
                    },
                )
            ),
            key="unsupported",
            purpose="editor.ground",
        )
        if not unsupported:
            return _EditResult(artifact, None, "")
        if attempt == 1:
            drifted = "; ".join(str(item.get("text", "")) for item in unsupported[:3])
            return _EditResult(
                artifact,
                GroundingDriftError.__name__,
                f"Piece {artifact.id!r} still carries unsupported assertions "
                f"after the cut pass: {drifted}",
            )
        artifact = decode_piece_payload(
            ctx.llm.complete(
                LLMRequest(
                    purpose="editor.cut",
                    instructions=ctx.specs.guardrail_text("sourcing"),
                    payload={
                        "piece_id": artifact.id,
                        "title": artifact.title,
                        "teaser": artifact.teaser,
                        "read_time_min": artifact.read_time_min,
                        "blocks": _blocks_payload(artifact),
                        "unsupported": list(unsupported),
                        "claims": claims,
                    },
                )
            ),
            piece_id=artifact.id,
            topic_ids=tuple(artifact.topic_ids),
            purpose="editor.cut",
        )
        residual = evaluate_piece(artifact, banned)
        if residual:
            summary = "; ".join(f"{v.code}: {v.message}" for v in residual[:3])
            return _EditResult(
                artifact,
                QABudgetExceededError.__name__,
                f"Piece {artifact.id!r} re-broke the guardrails while cutting drift: {summary}",
            )
    return _EditResult(artifact, None, "")
