"""The Reviewer — Stage 6, Constellation QA.

Asserts the Tier-1 outcome contract I1–I8 binary over the whole constellation
and judges the Tier-2 checks J1–J5, escalating any Tier-2 miss to the human
queue. A Tier-1 failure is fatal — the run either satisfies the contract or
fails, no soft warnings on the hard invariants.
"""

from harness.domain.qa_report import QAReport, parse_qa_outcome, render_qa_report
from harness.errors import ContractViolationError
from harness.guardrails.constellation import Tier2Judgement, evaluate_constellation
from harness.pipeline.context import RunContext
from harness.pipeline.decode import decode_object_list
from harness.pipeline.stages._kernel import (
    QA,
    assemble_constellation,
    expanded_prerequisites,
    load_plan,
)
from harness.ports.llm import LLMRequest


def run_stage_qa(ctx: RunContext) -> tuple[str, ...]:
    """Stage 6 — the Reviewer asserts I1–I8 binary and judges J1–J5.

    Args:
        ctx: The run context.

    Returns:
        The escalated Tier-2 codes (flags for the human queue).

    Raises:
        ContractViolationError: If any Tier-1 invariant fails — a run
            either satisfies the outcome contract or fails, no soft
            warnings on the hard invariants.
    """
    stage = ctx.manifest.stage("qa")
    plan = load_plan(ctx)
    ctx.workspace.require(stage.name, *expanded_prerequisites(stage, plan.concept_ids()))
    if ctx.workspace.exists(QA):
        _, escalations = parse_qa_outcome(ctx.workspace.read(QA))
        return escalations
    constellation = assemble_constellation(ctx)
    banned = ctx.specs.banned_phrases()
    tier1 = evaluate_constellation(constellation, banned)
    judged = decode_object_list(
        ctx.llm.complete(
            LLMRequest(
                purpose="reviewer.tier2",
                instructions=ctx.specs.guardrail_text("constellation"),
                payload={
                    "concepts": [
                        {
                            "id": concept.id,
                            "title": concept.title,
                            "premise": concept.premise,
                            "topics": list(concept.topic_ids),
                            "entry_worthy": concept.entry_worthy,
                        }
                        for concept in plan.concepts
                    ],
                    "connections": [
                        {"from": edge.from_piece_id, "to": edge.to_piece_id, "hook": edge.hook}
                        for edge in constellation.connections
                    ],
                },
            )
        ),
        key="judgements",
        purpose="reviewer.tier2",
    )
    tier2 = tuple(
        Tier2Judgement(
            code=str(item.get("code", "")),
            passed=bool(item.get("passed", False)),
            note=str(item.get("note", "")),
        )
        for item in judged
    )
    escalations = tuple(judgement.code for judgement in tier2 if not judgement.passed)
    ctx.workspace.write(
        QA, render_qa_report(QAReport(tier1=tier1, tier2=tier2, escalations=escalations))
    )
    if not tier1.passed:
        raise ContractViolationError(
            f"Tier-1 outcome contract failed: {', '.join(tier1.failed_codes())} — see qa.md"
        )
    return escalations
