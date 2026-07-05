"""The runtime-agnostic verdict contract (``feedback/verdicts.jsonl``, ADR 0013).

One append-only line per gate action, identical under either runtime.
Verdicts and edit-diffs never cross the ADR 0006 boundary — they are
generation-side learning signal for the Distiller and per-Topic calibration.
"""

import json
from collections.abc import Sequence
from dataclasses import dataclass, field

from harness.errors import MalformedArtifactError

VERDICT_VALUES = ("approve", "edit_approve", "reject")


@dataclass(frozen=True)
class VerdictRecord:
    """One gate action.

    Attributes:
        ts: ISO timestamp of the action.
        run_id: The run whose artifact was reviewed.
        runtime: Which orchestrator ran the pipeline (langgraph / claude-code).
        model: The model identity that produced the machine draft.
        gate: Which gate acted (``plan`` / ``piece`` / ``constellation``).
        target_id: What was reviewed — ``plan``, a Piece id, or
            ``constellation``.
        verdict: ``approve`` / ``edit_approve`` / ``reject``.
        reason: The human's reason (required for rejects, optional else).
        edit_diff: The unified machine→human diff, or None if the working
            copy matches the preserved machine draft.
        topics: The Topic ids the action concerns, for per-Topic calibration.
    """

    ts: str
    run_id: str
    runtime: str
    model: str
    gate: str
    target_id: str
    verdict: str
    reason: str = ""
    edit_diff: str | None = None
    topics: Sequence[str] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        """Normalize topics and validate the verdict value.

        Raises:
            MalformedArtifactError: If the verdict is not a known value.
        """
        object.__setattr__(self, "topics", tuple(self.topics))
        if self.verdict not in VERDICT_VALUES:
            raise MalformedArtifactError(
                f"verdict must be one of {VERDICT_VALUES}, got {self.verdict!r}"
            )

    def to_json_line(self) -> str:
        """Serialize to one JSONL line.

        Returns:
            The line, newline-terminated.
        """
        payload = {
            "ts": self.ts,
            "run_id": self.run_id,
            "runtime": self.runtime,
            "model": self.model,
            "gate": self.gate,
            "target_id": self.target_id,
            "verdict": self.verdict,
            "reason": self.reason,
            "edit_diff": self.edit_diff,
            "topics": list(self.topics),
        }
        return json.dumps(payload) + "\n"


def parse_verdict_line(line: str) -> VerdictRecord:
    """Parse one JSONL line back into a record.

    Args:
        line: The line text.

    Returns:
        The record.

    Raises:
        MalformedArtifactError: If the line is not a well-formed verdict.
    """
    try:
        payload = json.loads(line)
        return VerdictRecord(
            ts=str(payload["ts"]),
            run_id=str(payload["run_id"]),
            runtime=str(payload["runtime"]),
            model=str(payload["model"]),
            gate=str(payload["gate"]),
            target_id=str(payload["target_id"]),
            verdict=str(payload["verdict"]),
            reason=str(payload.get("reason", "")),
            edit_diff=payload.get("edit_diff"),
            topics=tuple(payload.get("topics", ())),
        )
    except (json.JSONDecodeError, KeyError, TypeError) as error:
        raise MalformedArtifactError(f"malformed verdict line: {error}") from error
