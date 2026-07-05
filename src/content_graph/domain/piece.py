"""Piece — the atomic unit of curated content."""

from collections.abc import Sequence
from dataclasses import dataclass, field

from content_graph.domain.blocks import ContentBlock
from content_graph.domain.errors import PieceValidationError
from content_graph.domain.validation import require_non_empty_strings


@dataclass(frozen=True)
class Piece:
    """One self-contained narrative, written into the Content Graph by generation.

    Attributes:
        id: Caller-supplied identity; upserts are idempotent by this id.
        title: The Piece's title.
        teaser: The entry lure shown when the Piece is an entry point
            (distinct from a Connection's hook, the onward lure).
        read_time_min: Approximate read time in minutes.
        blocks: The ordered body, as typed Content Blocks.
        topic_ids: The Topics this Piece belongs to — many, by design
            (ADR 0002). Deduplicated preserving first occurrence.
        run_id: Generation-run provenance, for debugging only. Never exposed
            through any read model (ADR 0006).
    """

    id: str
    title: str
    teaser: str
    read_time_min: int
    blocks: Sequence[ContentBlock] = field(default_factory=tuple)
    topic_ids: Sequence[str] = field(default_factory=tuple)
    run_id: str | None = None

    def __post_init__(self) -> None:
        """Normalize body and Topic tags to tuples and validate scalar fields.

        Raises:
            PieceValidationError: If id/title/teaser are blank or the
                read time is not a positive integer.
        """
        object.__setattr__(self, "blocks", tuple(self.blocks))
        object.__setattr__(self, "topic_ids", tuple(dict.fromkeys(self.topic_ids)))
        require_non_empty_strings(self, ("id", "title", "teaser"), PieceValidationError)
        if (
            not isinstance(self.read_time_min, int)
            or isinstance(self.read_time_min, bool)
            or self.read_time_min < 1
        ):
            raise PieceValidationError("Piece requires an integer read_time_min >= 1")
