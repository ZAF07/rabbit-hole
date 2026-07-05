"""Connection — a directed, editorially-authored edge between two Pieces.

A Connection is never a bare edge: it carries its own hook (the onward lure),
so the same destination reached from two origins can pitch two different
hooks. Connections are independent of the Topic taxonomy — cross-Topic jumps
are the product's most valuable content (ADR 0002).
"""

from dataclasses import dataclass

from content_graph.domain.errors import ConnectionValidationError
from content_graph.domain.validation import require_non_empty_strings


@dataclass(frozen=True)
class Connection:
    """A directed edge in the Content Graph; identity is ``(from, to)``.

    Attributes:
        from_piece_id: The origin Piece.
        to_piece_id: The destination Piece.
        hook: The per-origin lure that pitches the destination — distinct
            from the destination's own teaser (the entry lure).
    """

    from_piece_id: str
    to_piece_id: str
    hook: str

    def __post_init__(self) -> None:
        """Validate endpoints and hook.

        Raises:
            ConnectionValidationError: If an endpoint or the hook is blank,
                or the Connection points at its own origin.
        """
        require_non_empty_strings(
            self, ("from_piece_id", "to_piece_id", "hook"), ConnectionValidationError
        )
        if self.from_piece_id == self.to_piece_id:
            raise ConnectionValidationError("a Connection cannot point at its own origin Piece")
