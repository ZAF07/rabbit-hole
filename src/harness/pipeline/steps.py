"""Shared stage and gate state transitions — one decision logic, two runtimes.

Everything here is orchestration-agnostic: given the run context (and, where
needed, the accumulated run state), each function performs one pipeline step
and returns the state update. The LangGraph graph and the manifest runner
both dispatch to these, so only the *wiring* differs between runtimes
(ADR 0010) — decision logic can never drift apart.
"""

from collections.abc import Mapping

from harness.manifest import HumanGateSpec
from harness.pipeline import publish, stages
from harness.pipeline.context import RunContext
from harness.review.gates import GateStatus, preserve_and_decide

RunStateView = Mapping[str, object]


def string_list(state: RunStateView, key: str) -> list[str]:
    """Read a list-of-strings entry from the untyped run state.

    Args:
        state: The accumulated run state.
        key: The entry name.

    Returns:
        The list, or empty when absent.
    """
    value = state.get(key, [])
    return [str(item) for item in value] if isinstance(value, list) else []


def gate0_update(ctx: RunContext) -> dict[str, object]:
    """Stage 0 — refuse the run on missing DNA/Brief or placeholders.

    Args:
        ctx: The run's wiring.

    Returns:
        A failed state on refusal; empty otherwise.
    """
    reason = stages.run_stage_gate0(ctx)
    if reason:
        return {"status": "failed", "detail": f"stage 0 gate: {reason}"}
    return {}


def qa_update(ctx: RunContext) -> dict[str, object]:
    """Stage 6 — Constellation QA.

    Args:
        ctx: The run's wiring.

    Returns:
        The Tier-2 escalations recorded for the human queue.
    """
    return {"escalations": list(stages.run_stage_qa(ctx))}


def rewire_update(ctx: RunContext, state: RunStateView) -> dict[str, object]:
    """Publish step — the Weaver's second mode over the approved subset.

    Args:
        ctx: The run's wiring.
        state: The accumulated run state (for the rejected Pieces).

    Returns:
        The survivor set, or a failed state when nothing survived.
    """
    plan_artifact = stages.load_plan(ctx)
    rejected = set(string_list(state, "rejected_pieces"))
    survivors = frozenset(pid for pid in plan_artifact.concept_ids() if pid not in rejected)
    if not survivors:
        return {"status": "failed", "detail": "publish: every Piece was rejected"}
    publish.run_stage_rewire(ctx, survivors)
    return {"survivors": sorted(survivors)}


def reqa_update(ctx: RunContext, state: RunStateView) -> dict[str, object]:
    """Publish step — the Reviewer's second mode; flags the unfixable.

    Args:
        ctx: The run's wiring.
        state: The accumulated run state (for the survivor set).

    Returns:
        The re-validated survivors and the flagged Pieces.
    """
    survivors = frozenset(string_list(state, "survivors"))
    validated, flagged = publish.run_stage_reqa(ctx, survivors)
    return {"survivors": sorted(validated), "flagged_pieces": sorted(flagged)}


def write_update(ctx: RunContext, state: RunStateView) -> dict[str, object]:
    """Publish step — atomic write of the re-validated survivor set.

    Args:
        ctx: The run's wiring.
        state: The accumulated run state (for the survivor set).

    Returns:
        The completed state with the published Piece ids.
    """
    survivors = frozenset(string_list(state, "survivors"))
    published = publish.run_stage_write(ctx, survivors)
    return {"status": "completed", "published": list(published)}


def human_gate_update(ctx: RunContext, spec: HumanGateSpec) -> dict[str, object]:
    """Fire one human gate (ADR 0013) — identical under both runtimes.

    Args:
        ctx: The run's wiring.
        spec: The gate to fire.

    Returns:
        The state update — paused on a pending verdict, rejected for the
        whole-run gates, or the rejected-Piece list for the per-piece gate.
    """
    if spec.per_piece:
        rejected: list[str] = []
        for piece_id in stages.load_plan(ctx).concept_ids():
            decision = preserve_and_decide(ctx.workspace, ctx.gates, spec, piece_id)
            if decision.status is GateStatus.PENDING:
                return {
                    "status": "paused",
                    "detail": f"awaiting verdict at gate: {spec.name} {piece_id}",
                }
            if decision.status is GateStatus.REJECTED:
                rejected.append(piece_id)
        return {"rejected_pieces": rejected}
    decision = preserve_and_decide(ctx.workspace, ctx.gates, spec, spec.name)
    if decision.status is GateStatus.PENDING:
        return {"status": "paused", "detail": f"awaiting verdict at gate: {spec.name}"}
    if decision.status is GateStatus.REJECTED:
        return {"status": "rejected", "detail": f"{spec.name} rejected: {decision.reason}"}
    return {}
