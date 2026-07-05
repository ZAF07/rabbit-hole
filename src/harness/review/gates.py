"""Gate policies — how the pipeline asks for a human verdict at the three gates.

The gate points, machine-copy preservation, and verdict capture are shared
substrate identical under both runtimes; only the *policy* (auto-approve for
fixture runs, the file-workspace verdict contract for real ones) is swapped.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import StrEnum

from harness.manifest import HumanGateSpec
from harness.workspace import RunWorkspace


class GateStatus(StrEnum):
    """The three possible outcomes of asking a gate about one target."""

    APPROVED = "approved"
    REJECTED = "rejected"
    PENDING = "pending"


@dataclass(frozen=True)
class GateDecision:
    """One gate's answer for one target.

    Attributes:
        status: Approved / rejected / pending (no verdict recorded yet).
        reason: The human's reason, when one was recorded.
    """

    status: GateStatus
    reason: str = ""


class GatePolicy(ABC):
    """Decides gate outcomes; implementations never mutate deliverables."""

    @abstractmethod
    def decide(self, workspace: RunWorkspace, gate: HumanGateSpec, target_id: str) -> GateDecision:
        """Answer a gate for one target.

        Args:
            workspace: The run's file workspace.
            gate: The gate being asked.
            target_id: What is under review — ``"plan"``, a Piece id, or
                ``"constellation"``.

        Returns:
            The decision.
        """


def preserve_and_decide(
    workspace: RunWorkspace, policy: GatePolicy, gate: HumanGateSpec, target_id: str
) -> GateDecision:
    """The one review path both runtimes share at a human gate.

    Preserves the machine draft (diff-by-preservation, ADR 0013) and only
    then asks the policy — so the original is always intact before any
    human verdict can exist. A runtime that bypasses this helper diverges
    from the shared substrate and fails the parity test.

    Args:
        workspace: The run's file workspace.
        policy: The gate policy in force.
        gate: The gate being asked.
        target_id: What is under review — ``"plan"``, a Piece id, or
            ``"constellation"``.

    Returns:
        The decision.
    """
    workspace.preserve_machine_copy(gate.expand_target(target_id if gate.per_piece else None))
    return policy.decide(workspace, gate, target_id)


class AutoApproveGates(GatePolicy):
    """Approves everything — the fixture-run stand-in for the human arbiter."""

    def decide(self, workspace: RunWorkspace, gate: HumanGateSpec, target_id: str) -> GateDecision:
        """Approve unconditionally.

        Args:
            workspace: The run's file workspace (unused).
            gate: The gate being asked (unused).
            target_id: What is under review (unused).

        Returns:
            An approved decision.
        """
        return GateDecision(status=GateStatus.APPROVED)
