"""The Writer — Stage 3, closed-book drafting, per Piece.

The Writer's input is the vetted claim pack only; the draft is emitted as
ordered Content Blocks in the active Voice Profile (closed-book, ADR 0005).
"""

from harness.domain.grounding_io import ledger_from_json
from harness.domain.piece_io import render_piece
from harness.domain.plan import PieceConcept
from harness.pipeline.context import RunContext
from harness.pipeline.decode import decode_piece_payload
from harness.pipeline.stages._kernel import (
    _fan_out,
    draft_path,
    grounding_path,
    load_brief,
    load_plan,
    voice_name,
)
from harness.ports.llm import LLMRequest


def run_stage_draft(ctx: RunContext) -> None:
    """Stage 3 — the closed-book Writer, per Piece.

    The Writer's input is the vetted claim pack only; the draft is emitted
    as ordered Content Blocks in the active Voice Profile.

    Args:
        ctx: The run context.
    """
    stage = ctx.manifest.stage("draft")
    brief = load_brief(ctx)
    plan = load_plan(ctx)
    voice = ctx.specs.voice_text(voice_name(ctx, brief))
    dna = ctx.specs.dna_text()

    def work(concept: PieceConcept) -> None:
        if ctx.workspace.exists(draft_path(concept.id)):
            return
        ctx.workspace.require(
            stage.name, *(stage.expand(path, concept.id) for path in stage.prerequisites)
        )
        ledger = ledger_from_json(ctx.workspace.read(grounding_path(concept.id)))
        artifact = decode_piece_payload(
            ctx.llm.complete(
                LLMRequest(
                    purpose="writer.draft",
                    instructions=f"{dna}\n\n---\n\n{voice}",
                    payload={
                        "piece_id": concept.id,
                        "title": concept.title,
                        "premise": concept.premise,
                        "topics": list(concept.topic_ids),
                        "claims": [
                            {"id": claim.id, "text": claim.text}
                            for claim in ledger.verified_claims()
                        ],
                    },
                )
            ),
            piece_id=concept.id,
            topic_ids=tuple(concept.topic_ids),
            purpose="writer.draft",
        )
        ctx.workspace.write(draft_path(concept.id), render_piece(artifact))

    _fan_out(ctx, plan.concepts, work)
