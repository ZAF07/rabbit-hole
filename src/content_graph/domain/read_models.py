"""Read models returned by the repository port's read surface.

These are what consumption sees. They deliberately exclude every
generation-only field — run_id, constellation, grounding ledger — so the
boundary of ADR 0006 cannot leak into the experience.
"""

from dataclasses import dataclass, field

from content_graph.domain.blocks import ContentBlock


@dataclass(frozen=True)
class TopicRead:
    """A Topic as consumption reads it, carrying its DAG parents.

    Attributes:
        id: The Topic's identity.
        slug: URL-safe unique name.
        title: Display title.
        parent_ids: Ids of the Topic's parents (zero or more — the DAG),
            sorted for determinism.
    """

    id: str
    slug: str
    title: str
    parent_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class PieceSummary:
    """A Piece's entry-surface view: teaser and Topics, no body.

    Attributes:
        id: The Piece's identity.
        title: The Piece's title.
        teaser: The entry lure for entry-point surfaces.
        read_time_min: Approximate read time in minutes.
        topics: The Topics this Piece belongs to, sorted by slug.
    """

    id: str
    title: str
    teaser: str
    read_time_min: int
    topics: tuple[TopicRead, ...] = ()


@dataclass(frozen=True)
class ConnectionPreview:
    """An outbound Connection joined with what a preview card needs.

    Carries the destination's title and Topics alongside the hook so the
    reader renders onward preview cards without a second round-trip.

    Attributes:
        from_piece_id: The origin Piece.
        to_piece_id: The destination Piece.
        hook: The per-origin onward lure.
        to_title: The destination Piece's title.
        to_topics: The destination Piece's Topics, sorted by slug.
    """

    from_piece_id: str
    to_piece_id: str
    hook: str
    to_title: str
    to_topics: tuple[TopicRead, ...] = ()


@dataclass(frozen=True)
class PieceRead:
    """A Piece as consumption reads it: full ordered body, no provenance.

    Attributes:
        id: The Piece's identity.
        title: The Piece's title.
        teaser: The entry lure for entry-point surfaces.
        read_time_min: Approximate read time in minutes.
        blocks: The ordered, typed body.
        topics: The Topics this Piece belongs to, sorted by slug.
    """

    id: str
    title: str
    teaser: str
    read_time_min: int
    blocks: tuple[ContentBlock, ...]
    topics: tuple[TopicRead, ...] = field(default_factory=tuple)
