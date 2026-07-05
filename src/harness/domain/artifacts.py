"""Generation-side working artifacts the guardrail evaluators judge.

These are deliberately lenient — unlike the Content Graph's own domain types,
they tolerate missing or malformed fields, because deciding whether a field
is missing (invariant I2) is the evaluators' job, not a construction error.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from content_graph.domain.blocks import BlockKind, ContentBlock
from harness.domain.grounding import GroundingLedger


def block_text(block: ContentBlock) -> str:
    """Extract the human-readable text carried by a Content Block.

    Args:
        block: Any V1 text block.

    Returns:
        The block's prose — for a stat-callout, value and label joined.
    """
    if block.kind is BlockKind.STAT_CALLOUT:
        value = block.payload.get("value", "")
        label = block.payload.get("label", "")
        return f"{value} {label}".strip()
    text = block.payload.get("text", "")
    return text if isinstance(text, str) else ""


@dataclass(frozen=True)
class PieceArtifact:
    """A Piece as the harness works on it — draft or final.

    Attributes:
        id: The Piece identity within the run.
        title: The Piece's title (may be blank in a broken artifact).
        teaser: The entry lure (may be blank in a broken artifact).
        read_time_min: Approximate read time; 0 when unset.
        topic_ids: The Topic tags the plan assigned.
        blocks: The ordered body as Content Blocks.
    """

    id: str
    title: str = ""
    teaser: str = ""
    read_time_min: int = 0
    topic_ids: Sequence[str] = field(default_factory=tuple)
    blocks: Sequence[ContentBlock] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        """Normalize sequence fields to tuples."""
        object.__setattr__(self, "topic_ids", tuple(self.topic_ids))
        object.__setattr__(self, "blocks", tuple(self.blocks))

    def paragraphs(self) -> tuple[str, ...]:
        """Return the text of every paragraph block, in order.

        Returns:
            The paragraph texts.
        """
        return tuple(
            block_text(block) for block in self.blocks if block.kind is BlockKind.PARAGRAPH
        )

    def all_text(self) -> str:
        """Return the Piece's full prose surface for phrase-level checks.

        Returns:
            Title, teaser, and every block's text joined by newlines.
        """
        parts = [self.title, self.teaser, *(block_text(block) for block in self.blocks)]
        return "\n".join(part for part in parts if part)


@dataclass(frozen=True)
class WiredConnection:
    """A realized Connection as the Weaver emits it.

    Attributes:
        from_piece_id: The origin Piece.
        to_piece_id: The destination Piece.
        hook: The per-origin lure (may be blank in a broken artifact).
        rationale: The stated relationship that earns the jump — what makes
            this a real Connection rather than shared-Topic adjacency.
    """

    from_piece_id: str
    to_piece_id: str
    hook: str = ""
    rationale: str = ""

    def subject(self) -> str:
        """Return the Connection's display identity for violation reports.

        Returns:
            ``"<from>-><to>"``.
        """
        return f"{self.from_piece_id}->{self.to_piece_id}"


@dataclass(frozen=True)
class ConstellationArtifact:
    """One run's whole output, assembled for constellation-level QA.

    Attributes:
        pieces: The finished Piece artifacts.
        connections: The wired Connections.
        ledgers: Grounding ledger per Piece id (invariant I8's input).
        piece_count_target: Inclusive (min, max) from the Theme Brief (I1).
        target_topic_ids: The Topics the Brief requires the run to span (I3).
    """

    pieces: Sequence[PieceArtifact] = field(default_factory=tuple)
    connections: Sequence[WiredConnection] = field(default_factory=tuple)
    ledgers: Mapping[str, GroundingLedger] = field(default_factory=dict)
    piece_count_target: tuple[int, int] = (1, 10_000)
    target_topic_ids: Sequence[str] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        """Normalize collections to immutable-friendly copies."""
        object.__setattr__(self, "pieces", tuple(self.pieces))
        object.__setattr__(self, "connections", tuple(self.connections))
        object.__setattr__(self, "ledgers", dict(self.ledgers))
        object.__setattr__(self, "target_topic_ids", tuple(self.target_topic_ids))

    def piece_ids(self) -> frozenset[str]:
        """Return the set of Piece ids in the constellation.

        Returns:
            The ids.
        """
        return frozenset(piece.id for piece in self.pieces)

    def topics_by_piece(self) -> dict[str, frozenset[str]]:
        """Return each Piece's Topic set, keyed by Piece id.

        Returns:
            Piece id → its Topic ids.
        """
        return {piece.id: frozenset(piece.topic_ids) for piece in self.pieces}
