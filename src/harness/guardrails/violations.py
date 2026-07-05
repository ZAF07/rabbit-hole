"""The violation record every guardrail evaluator returns."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Violation:
    """One specific, binary guardrail failure.

    Attributes:
        code: The check that failed — e.g. ``"A1"``, ``"D3"``, ``"I4"`` —
            as named in the corresponding ``harness/guardrails/*.md`` spec.
        subject: What failed — a Piece id, a Connection ``"<from>-><to>"``, or
            ``"constellation"``.
        message: Why it failed, concretely.
        excerpt: The offending text, quoted, when there is one.
    """

    code: str
    subject: str
    message: str
    excerpt: str | None = None
