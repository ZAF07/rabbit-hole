"""Wire DTOs — the JSON the reader client receives.

Each DTO mirrors an application read model one-to-one and carries **only**
Pieces / Connections / Topics fields in **internal** vocabulary. Nothing
generation-only (``run_id``, constellation) is reachable — the read models
already exclude it (ADR 0006) — and no branded string ("Thread", "Tapestry")
is emitted: those render client-side from the presentation vocabulary module
(ADR 0001). The converters are the single translation point from domain read
models to the wire.
"""

from typing import Any

from pydantic import BaseModel

from consumption.domain.read_models import (
    DailyFeatureView,
    DailyNotification,
    JourneyView,
    PersonalKnowledgeGraph,
    ReadingView,
    ResumeView,
)
from content_graph.domain.blocks import ContentBlock
from content_graph.domain.read_models import (
    ConnectionPreview,
    PieceRead,
    PieceSummary,
    TopicRead,
)


class TopicDTO(BaseModel):
    """A Topic as the wire carries it — what a node is coloured and clustered by."""

    id: str
    slug: str
    title: str
    parent_ids: list[str]


class ContentBlockDTO(BaseModel):
    """One element of a Piece's ordered body: its kind and typed payload."""

    kind: str
    payload: dict[str, Any]


class PieceSummaryDTO(BaseModel):
    """A Piece's entry surface: teaser and Topics, no body."""

    id: str
    title: str
    teaser: str
    read_time_min: int
    topics: list[TopicDTO]


class ConnectionPreviewDTO(BaseModel):
    """An outbound Connection with what an onward preview card needs."""

    from_piece_id: str
    to_piece_id: str
    hook: str
    to_title: str
    to_topics: list[TopicDTO]


class PieceReadDTO(BaseModel):
    """A Piece open for reading: its full ordered body."""

    id: str
    title: str
    teaser: str
    read_time_min: int
    blocks: list[ContentBlockDTO]
    topics: list[TopicDTO]


class DailyFeatureDTO(BaseModel):
    """The front door: the day's featured Piece plus its onward peek."""

    piece: PieceSummaryDTO
    connections: list[ConnectionPreviewDTO]


class ReadingDTO(BaseModel):
    """A Piece open for reading and where it Connects onward."""

    piece: PieceReadDTO
    connections: list[ConnectionPreviewDTO]


class JourneyDTO(BaseModel):
    """Where the reader stands on their durable path."""

    current_piece_id: str | None
    stack: list[str]
    depth: int


class ResumeDTO(BaseModel):
    """The continue-your-thread surface: current Piece, restored stack, Session."""

    reading: ReadingDTO
    stack: list[str]
    session_id: str


class KnowledgeGraphNodeDTO(BaseModel):
    """A Piece the reader has read — a node in their trail."""

    piece_id: str
    title: str
    topics: list[TopicDTO]


class KnowledgeGraphEdgeDTO(BaseModel):
    """A Connection the reader pulled — an edge in their trail."""

    from_piece_id: str
    to_piece_id: str


class KnowledgeGraphDTO(BaseModel):
    """The reader's own trail: distinct Pieces read, Connections pulled."""

    nodes: list[KnowledgeGraphNodeDTO]
    edges: list[KnowledgeGraphEdgeDTO]


class NotificationDTO(BaseModel):
    """The day's single dignified curiosity nudge, pointing at the Piece it opens."""

    piece_id: str
    title: str
    teaser: str


class PullRequest(BaseModel):
    """A request to pull a Connection: the origin the reader stands on and its destination."""

    from_piece_id: str
    to_piece_id: str


def _topic_dto(topic: TopicRead) -> TopicDTO:
    """Convert a Topic read model to its wire DTO."""
    return TopicDTO(
        id=topic.id,
        slug=topic.slug,
        title=topic.title,
        parent_ids=list(topic.parent_ids),
    )


def _block_dto(block: ContentBlock) -> ContentBlockDTO:
    """Convert a Content Block to its wire DTO, kind rendered as its string value."""
    return ContentBlockDTO(kind=block.kind.value, payload=dict(block.payload))


def _piece_summary_dto(piece: PieceSummary) -> PieceSummaryDTO:
    """Convert a Piece entry summary to its wire DTO."""
    return PieceSummaryDTO(
        id=piece.id,
        title=piece.title,
        teaser=piece.teaser,
        read_time_min=piece.read_time_min,
        topics=[_topic_dto(topic) for topic in piece.topics],
    )


def _piece_read_dto(piece: PieceRead) -> PieceReadDTO:
    """Convert a fully-read Piece to its wire DTO."""
    return PieceReadDTO(
        id=piece.id,
        title=piece.title,
        teaser=piece.teaser,
        read_time_min=piece.read_time_min,
        blocks=[_block_dto(block) for block in piece.blocks],
        topics=[_topic_dto(topic) for topic in piece.topics],
    )


def _connection_dto(connection: ConnectionPreview) -> ConnectionPreviewDTO:
    """Convert an outbound Connection preview to its wire DTO."""
    return ConnectionPreviewDTO(
        from_piece_id=connection.from_piece_id,
        to_piece_id=connection.to_piece_id,
        hook=connection.hook,
        to_title=connection.to_title,
        to_topics=[_topic_dto(topic) for topic in connection.to_topics],
    )


def daily_feature_dto(view: DailyFeatureView) -> DailyFeatureDTO:
    """Convert the Daily Feature view to its wire DTO."""
    return DailyFeatureDTO(
        piece=_piece_summary_dto(view.piece),
        connections=[_connection_dto(connection) for connection in view.connections],
    )


def reading_dto(view: ReadingView) -> ReadingDTO:
    """Convert a reading view to its wire DTO."""
    return ReadingDTO(
        piece=_piece_read_dto(view.piece),
        connections=[_connection_dto(connection) for connection in view.connections],
    )


def journey_dto(view: JourneyView) -> JourneyDTO:
    """Convert a journey view to its wire DTO."""
    return JourneyDTO(
        current_piece_id=view.current_piece_id,
        stack=list(view.stack),
        depth=view.depth,
    )


def resume_dto(view: ResumeView) -> ResumeDTO:
    """Convert a resume view to its wire DTO."""
    return ResumeDTO(
        reading=reading_dto(view.reading),
        stack=list(view.stack),
        session_id=view.session_id,
    )


def knowledge_graph_dto(graph: PersonalKnowledgeGraph) -> KnowledgeGraphDTO:
    """Convert the reader's Personal Knowledge Graph to its wire DTO."""
    return KnowledgeGraphDTO(
        nodes=[
            KnowledgeGraphNodeDTO(
                piece_id=node.piece_id,
                title=node.title,
                topics=[_topic_dto(topic) for topic in node.topics],
            )
            for node in graph.nodes
        ],
        edges=[
            KnowledgeGraphEdgeDTO(from_piece_id=edge.from_piece_id, to_piece_id=edge.to_piece_id)
            for edge in graph.edges
        ],
    )


def notification_dto(notification: DailyNotification) -> NotificationDTO:
    """Convert the daily notification to its wire DTO."""
    return NotificationDTO(
        piece_id=notification.piece_id,
        title=notification.title,
        teaser=notification.teaser,
    )
