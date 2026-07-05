"""Connection & hook checks (``harness/guardrails/connection.md``) as pure functions.

Mechanical, binary FAIL-if rules over a Connection set. Judgment checks
(truth of the relationship, clickbait, voice) are enumerated in
:data:`JUDGED_CONNECTION_CHECKS` for the LLM judge.
"""

import re
from collections.abc import Mapping, Sequence

from harness.domain.artifacts import WiredConnection
from harness.guardrails.phrases import compile_phrase
from harness.guardrails.violations import Violation

JUDGED_CONNECTION_CHECKS: Mapping[str, str] = {
    "A2": "the connecting relationship is true, not a rhetorical bridge",
    "A3": "prizes the non-obvious honestly — surprise never overrides truth",
    "A4": "the hook's promise matches what the destination delivers",
    "B2": "the hook pays off — no clickbait the Piece can't honor",
    "B4": "the hook is voice-conformant micro-copy",
}

_GENERIC_ADJACENCY = re.compile(
    r"\bboth\s+(?:are\s+)?(?:about|cover|concern|discuss|deal\s+with)\b"
    r"|\bsame\s+(?:topic|subject|field)\b"
    r"|\brelated\s+(?:topic|subject)s?\b"
    r"|\balso\s+about\b",
    re.IGNORECASE,
)
_GENERIC_LURE = re.compile(
    r"^(?:learn|read|find\s+out|discover|explore)\b(?:\s+more)?(?:\s+about)?\b",
    re.IGNORECASE,
)


def _normalized(hook: str) -> str:
    """Collapse a hook to its comparison form for B3.

    Args:
        hook: The hook text.

    Returns:
        Case-folded, whitespace-collapsed text.
    """
    return " ".join(hook.split()).casefold()


def evaluate_connections(
    connections: Sequence[WiredConnection], banned_phrases: Sequence[str]
) -> tuple[Violation, ...]:
    """Run every mechanical Connection/hook check over a Connection set.

    Set-level because B3 (a hook identical from any origin) is only
    decidable across edges sharing a destination.

    Args:
        connections: The wired Connections to judge.
        banned_phrases: The banned-filler list (B5 inherits piece D3).

    Returns:
        Every violation found, sorted by code then subject.
    """
    violations: list[Violation] = []
    for connection in connections:
        rationale = connection.rationale.strip()
        if not rationale or _GENERIC_ADJACENCY.search(rationale):
            violations.append(
                Violation(
                    code="A1",
                    subject=connection.subject(),
                    message="shared-Topic adjacency, not a real specific relationship",
                    excerpt=rationale or None,
                )
            )
        hook = connection.hook.strip()
        if not hook or _GENERIC_LURE.match(hook):
            violations.append(
                Violation(
                    code="B1",
                    subject=connection.subject(),
                    message="hook opens no specific curiosity gap",
                    excerpt=hook or None,
                )
            )
        for phrase in banned_phrases:
            if compile_phrase(phrase).search(hook):
                violations.append(
                    Violation(
                        code="B5",
                        subject=connection.subject(),
                        message="banned-filler phrase in hook",
                        excerpt=phrase,
                    )
                )

    by_destination: dict[str, dict[str, list[WiredConnection]]] = {}
    for connection in connections:
        hooks = by_destination.setdefault(connection.to_piece_id, {})
        hooks.setdefault(_normalized(connection.hook), []).append(connection)
    for destination, hooks in sorted(by_destination.items()):
        for text, edges in hooks.items():
            if text and len(edges) > 1:
                origins = ", ".join(sorted(edge.from_piece_id for edge in edges))
                violations.append(
                    Violation(
                        code="B3",
                        subject=f"->{destination}",
                        message=f"hook reads identically from origins [{origins}] — "
                        "not specific to the pair",
                        excerpt=edges[0].hook,
                    )
                )
    return tuple(sorted(violations, key=lambda v: (v.code, v.subject, v.message)))
