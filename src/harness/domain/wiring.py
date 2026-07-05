"""Serialize/parse the Weaver's deliverable (``connections.md``)."""

import re

from harness.domain.artifacts import WiredConnection
from harness.errors import MalformedArtifactError

_EDGE_LINE = re.compile(
    r"^- (?P<from>[\w-]+) -> (?P<to>[\w-]+) \| hook: (?P<hook>.+?) \| rationale: (?P<rationale>.+)$"
)


def render_connections(connections: tuple[WiredConnection, ...]) -> str:
    """Serialize wired Connections to deliverable text.

    Args:
        connections: The realized Connections with their per-origin hooks.

    Returns:
        The deliverable text.
    """
    lines = ["## Connections", ""]
    lines.extend(
        f"- {edge.from_piece_id} -> {edge.to_piece_id} | hook: {edge.hook}"
        f" | rationale: {edge.rationale}"
        for edge in connections
    )
    return "\n".join(lines).rstrip() + "\n"


def parse_connections(text: str) -> tuple[WiredConnection, ...]:
    """Parse ``connections.md`` text back into wired Connections.

    Args:
        text: The deliverable text (possibly human-edited).

    Returns:
        The Connections, in document order.

    Raises:
        MalformedArtifactError: If no Connections could be parsed.
    """
    edges = [
        WiredConnection(
            from_piece_id=match.group("from"),
            to_piece_id=match.group("to"),
            hook=match.group("hook").strip(),
            rationale=match.group("rationale").strip(),
        )
        for line in text.splitlines()
        if (match := _EDGE_LINE.match(line.strip()))
    ]
    if not edges:
        raise MalformedArtifactError("connections.md contains no Connections")
    return tuple(edges)
