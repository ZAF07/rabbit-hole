"""The review surface — verdict capture over the file workspace (ADR 0013).

Diff by preservation: the machine's output is kept as ``*.machine.md``, the
human edits the working copy, and recording an approval computes the unified
machine→human diff — the richest learning signal. The surface is shared
substrate: both runtimes preserve drafts, pause, and append the same
``feedback/verdicts.jsonl``; only the front-end differs.
"""

import difflib
from datetime import UTC, datetime

from harness.domain.piece_io import parse_piece
from harness.domain.plan import parse_plan
from harness.domain.verdicts import VerdictRecord, parse_verdict_line
from harness.errors import HarnessError, MalformedArtifactError
from harness.manifest import HumanGateSpec
from harness.review.gates import GateDecision, GatePolicy, GateStatus
from harness.workspace import RunWorkspace

VERDICTS_PATH = "feedback/verdicts.jsonl"


def read_verdicts(workspace: RunWorkspace) -> tuple[VerdictRecord, ...]:
    """Read every recorded verdict, in append order.

    Args:
        workspace: The run's file workspace.

    Returns:
        The records; empty if no verdict has been recorded yet.
    """
    if not workspace.exists(VERDICTS_PATH):
        return ()
    return tuple(
        parse_verdict_line(line)
        for line in workspace.read(VERDICTS_PATH).splitlines()
        if line.strip()
    )


def machine_diff(workspace: RunWorkspace, target: str) -> str | None:
    """Compute the unified machine→human diff for one reviewed artifact.

    Args:
        workspace: The run's file workspace.
        target: The workspace-relative working-copy path.

    Returns:
        The unified diff from the preserved ``*.machine`` copy to the
        working copy, or None if they are identical (or either is absent).
    """
    working = workspace.path(target)
    machine = working.with_name(f"{working.stem}.machine{working.suffix}")
    if not machine.is_file() or not working.is_file():
        return None
    machine_text = machine.read_text()
    working_text = working.read_text()
    if machine_text == working_text:
        return None
    lines = difflib.unified_diff(
        machine_text.splitlines(keepends=True),
        working_text.splitlines(keepends=True),
        fromfile=f"{target} (machine)",
        tofile=f"{target} (human)",
    )
    return "".join(lines)


def _topics_for(workspace: RunWorkspace, gate: HumanGateSpec, target_id: str) -> tuple[str, ...]:
    """Resolve the Topic ids a gate action concerns (per-Topic calibration).

    Args:
        workspace: The run's file workspace.
        gate: The gate acting.
        target_id: The review target.

    Returns:
        The Piece's Topics for the piece gate; the plan's Topic union for
        the plan and constellation gates; empty if nothing is parseable.
    """
    try:
        if gate.per_piece:
            artifact = parse_piece(workspace.read(gate.expand_target(target_id)))
            return tuple(artifact.topic_ids)
        plan = parse_plan(workspace.read("plan.md"))
        return tuple(sorted({topic for concept in plan.concepts for topic in concept.topic_ids}))
    except HarnessError:
        return ()


def record_verdict(
    workspace: RunWorkspace,
    gate: HumanGateSpec,
    target_id: str,
    verdict: str,
    *,
    run_id: str,
    runtime: str,
    model: str,
    reason: str = "",
) -> VerdictRecord:
    """Record one gate action to the append-only verdict log.

    An ``approve`` on an edited working copy is recorded as
    ``edit_approve`` with the unified machine→human diff attached — the
    diff, not the caller, is what distinguishes the two.

    Args:
        workspace: The run's file workspace.
        gate: The gate acting.
        target_id: What was reviewed — ``plan``, a Piece id, or
            ``constellation``.
        verdict: ``approve`` / ``edit_approve`` / ``reject``.
        run_id: The run's identity.
        runtime: The orchestrator recording the verdict.
        model: The model that produced the machine draft.
        reason: The human's reason — required for rejects, since the
            Distiller learns from it.

    Returns:
        The appended record.

    Raises:
        MalformedArtifactError: If a reject carries no reason.
    """
    if verdict == "reject" and not reason.strip():
        raise MalformedArtifactError(f"a reject verdict on {target_id!r} requires a reason")
    target = gate.expand_target(target_id if gate.per_piece else None)
    diff = machine_diff(workspace, target)
    if verdict == "approve" and diff is not None:
        verdict = "edit_approve"
    record = VerdictRecord(
        ts=datetime.now(tz=UTC).isoformat(),
        run_id=run_id,
        runtime=runtime,
        model=model,
        gate=gate.name,
        target_id=target_id,
        verdict=verdict,
        reason=reason,
        edit_diff=diff,
        topics=_topics_for(workspace, gate, target_id),
    )
    workspace.append(VERDICTS_PATH, record.to_json_line())
    return record


class WorkspaceVerdictGates(GatePolicy):
    """The real gate policy: a gate answers what ``verdicts.jsonl`` recorded.

    No verdict for a target means the run pauses there — the human reviews
    the workspace, records a verdict (Claude Code is the V1 front-end), and
    re-invokes the run, which resumes off its deliverables.
    """

    def decide(self, workspace: RunWorkspace, gate: HumanGateSpec, target_id: str) -> GateDecision:
        """Answer a gate from the recorded verdicts; the latest one wins.

        Args:
            workspace: The run's file workspace.
            gate: The gate being asked.
            target_id: The review target.

        Returns:
            Approved for approve/edit_approve, rejected with the recorded
            reason for reject, pending when no verdict exists yet.
        """
        latest: VerdictRecord | None = None
        for record in read_verdicts(workspace):
            if record.gate == gate.name and record.target_id == target_id:
                latest = record
        if latest is None:
            return GateDecision(status=GateStatus.PENDING)
        if latest.verdict == "reject":
            return GateDecision(status=GateStatus.REJECTED, reason=latest.reason)
        return GateDecision(status=GateStatus.APPROVED, reason=latest.reason)
