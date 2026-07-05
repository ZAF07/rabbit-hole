"""Read models the reader use-cases return.

These compose the Content Graph's own boundary-safe read models — ``PieceRead``,
``PieceSummary``, ``ConnectionPreview`` — into the surfaces the reader renders.
They carry the two lures without ever conflating them: an entry surface leads
with the Piece's own ``teaser``; each onward step leads with the Connection's
``hook``. Nothing generation-only (``run_id``, constellation) is reachable
through any of them (ADR 0006).
"""

from dataclasses import dataclass

from content_graph.domain.read_models import (
    ConnectionPreview,
    PieceRead,
    PieceSummary,
    TopicRead,
)


@dataclass(frozen=True)
class DailyFeatureView:
    """The app's front door: the day's featured Piece as an entry surface.

    Leads with the Piece's ``teaser`` (the entry lure) and lets the reader
    peek at where it Connects onward before committing to read.

    Attributes:
        piece: The featured Piece's entry summary (teaser, Topics, no body).
        connections: The onward Connection previews — the up-front peek.
    """

    piece: PieceSummary
    connections: tuple[ConnectionPreview, ...]


@dataclass(frozen=True)
class ReadingView:
    """A Piece open for reading: its full ordered body and where it Connects.

    Leads with the Piece's Content Blocks; each onward preview carries the
    Connection's ``hook`` (the onward lure), joined to the destination's
    title and Topics so a preview card renders without a second round-trip.

    Attributes:
        piece: The Piece with its full ordered, typed body.
        connections: The onward Connection previews (hook + destination facts).
    """

    piece: PieceRead
    connections: tuple[ConnectionPreview, ...]


@dataclass(frozen=True)
class JourneyView:
    """Where the reader stands on their durable path.

    Attributes:
        current_piece_id: The Piece the reader is on, or None if unstarted.
        stack: The backtrack stack, root -> current — the way they came.
        depth: Distinct Pieces visited — the ground their curiosity covered.
    """

    current_piece_id: str | None
    stack: tuple[str, ...]
    depth: int


@dataclass(frozen=True)
class ResumeView:
    """The "continue your thread" surface: the reader picked up where they left.

    Attributes:
        reading: The current Piece, open and ready to continue reading.
        stack: The restored backtrack stack — the way they came.
        session_id: The analytics Session the resume runs in (a fresh one when
            resuming after the window had closed).
    """

    reading: "ReadingView"
    stack: tuple[str, ...]
    session_id: str


@dataclass(frozen=True)
class DailyNotification:
    """One dignified daily nudge teasing the day's real hook (ADR 0009).

    Carries the Daily Feature's own teaser — the genuine open loop the Piece
    closes — and points at the very Piece it opens, so there is never a
    bait-and-switch. No streak, badge, point, or leaderboard has any place here.

    Attributes:
        piece_id: The Piece the notification opens — the actual Daily Feature.
        title: The Daily Feature's title.
        teaser: The real hook, held to the same anti-clickbait bar as in-app.
    """

    piece_id: str
    title: str
    teaser: str


@dataclass(frozen=True)
class PersonalKnowledgeGraphNode:
    """A Piece the reader has read — a node in their Personal Knowledge Graph.

    Attributes:
        piece_id: The Piece this node stands for; re-entering it makes it a
            re-entry point (reread, or pull a different fork).
        title: The Piece's title.
        topics: The Piece's Topics — what the node is coloured and clustered by.
    """

    piece_id: str
    title: str
    topics: tuple[TopicRead, ...]


@dataclass(frozen=True)
class PersonalKnowledgeGraphEdge:
    """A Connection the reader pulled — an edge in their Personal Knowledge Graph.

    Attributes:
        from_piece_id: The node the reader pulled from.
        to_piece_id: The node the reader pulled to.
    """

    from_piece_id: str
    to_piece_id: str


@dataclass(frozen=True)
class PersonalKnowledgeGraph:
    """The reader's own trail: the subgraph of the Content Graph they traversed.

    The deduped union of the reader's Session paths — nodes are the distinct
    Pieces they read, edges are the Connections they pulled, and each node
    carries its Topics so the client can colour and cluster by Topic. Shown in
    V1; personalized-from in Phase 2 (same asset — ADR 0009). This is the
    internal name; the UI renders it as its branded surface term.

    Attributes:
        nodes: The distinct Pieces read, in first-visit order.
        edges: The Connections pulled, in the order they were pulled.
    """

    nodes: tuple[PersonalKnowledgeGraphNode, ...]
    edges: tuple[PersonalKnowledgeGraphEdge, ...]


def summarize(piece: PieceRead) -> PieceSummary:
    """Reduce a fully-read Piece to its entry-surface summary.

    Args:
        piece: The Piece read model, body included.

    Returns:
        The entry summary — teaser, Topics, read time — without the body.
    """
    return PieceSummary(
        id=piece.id,
        title=piece.title,
        teaser=piece.teaser,
        read_time_min=piece.read_time_min,
        topics=piece.topics,
    )


__all__ = [
    "ConnectionPreview",
    "DailyFeatureView",
    "DailyNotification",
    "JourneyView",
    "PieceRead",
    "PieceSummary",
    "PersonalKnowledgeGraph",
    "PersonalKnowledgeGraphEdge",
    "PersonalKnowledgeGraphNode",
    "ReadingView",
    "ResumeView",
    "TopicRead",
    "summarize",
]
