"""A small fixture constellation the reader loop is exercised over.

Four Pieces joined by Connections, plus a Daily Feature, seeded into any
``ContentGraphRepository`` through its write surface. Shapes the graph so the
whole reader loop — enter, read, pull, backtrack, revisit, resume, Tapestry —
is exercisable offline against the in-memory fake.

    container ──▶ logistics ──▶ jit
        │                        ▲
        └────────▶ mclean ───────┘
        ▲                        │
        └──────────(jit)◀────────┘   (jit ──▶ container closes a loop)
"""

from datetime import date

from content_graph.domain.blocks import BlockKind, ContentBlock
from content_graph.domain.connection import Connection
from content_graph.domain.piece import Piece
from content_graph.domain.topic import Topic
from content_graph.ports.repository import ContentGraphRepository

CONTAINER = "piece-container"
LOGISTICS = "piece-logistics"
MCLEAN = "piece-mclean"
JIT = "piece-jit"

ECONOMICS = "topic-economics"
HISTORY = "topic-history"
TECHNOLOGY = "topic-technology"

TODAY = date(2026, 7, 5)


def _container_body() -> tuple[ContentBlock, ...]:
    return (
        ContentBlock(BlockKind.HEADING, {"text": "The box that ate the docks", "level": 1}),
        ContentBlock(BlockKind.PARAGRAPH, {"text": "Before the container, cargo moved by hand."}),
        ContentBlock(
            BlockKind.PULL_QUOTE,
            {"text": "The ship was the cheap part.", "attribution": "Marc Levinson"},
        ),
        ContentBlock(BlockKind.STAT_CALLOUT, {"value": "90%", "label": "of trade moves by sea"}),
        ContentBlock(BlockKind.PARAGRAPH, {"text": "Then one trucker changed the economics."}),
    )


def _paragraph(piece_id: str) -> tuple[ContentBlock, ...]:
    return (ContentBlock(BlockKind.PARAGRAPH, {"text": f"The body of {piece_id}."}),)


def seed(repo: ContentGraphRepository, *, feature_on: date = TODAY) -> None:
    """Write the fixture constellation into ``repo`` through its write surface.

    Args:
        repo: The Content Graph repository to seed.
        feature_on: The date the container Piece fronts the app.
    """
    for topic_id, slug, title in (
        (ECONOMICS, "economics", "Economics"),
        (HISTORY, "history", "History"),
        (TECHNOLOGY, "technology", "Technology"),
    ):
        repo.upsert_topic(Topic(id=topic_id, slug=slug, title=title))

    repo.upsert_piece(
        Piece(
            id=CONTAINER,
            title="The Shipping Container",
            teaser="How a steel box rewired the world economy.",
            read_time_min=6,
            blocks=_container_body(),
            topic_ids=(ECONOMICS, HISTORY),
            run_id="run-generation-42",
        )
    )
    repo.upsert_piece(
        Piece(
            id=LOGISTICS,
            title="The Ballet of the Cranes",
            teaser="Choreography no human could keep in their head.",
            read_time_min=5,
            blocks=_paragraph(LOGISTICS),
            topic_ids=(TECHNOLOGY,),
        )
    )
    repo.upsert_piece(
        Piece(
            id=MCLEAN,
            title="The Trucker Who Rebuilt the Sea",
            teaser="He looked at a ship and saw everything wrong.",
            read_time_min=4,
            blocks=_paragraph(MCLEAN),
            topic_ids=(HISTORY,),
        )
    )
    repo.upsert_piece(
        Piece(
            id=JIT,
            title="Just in Time",
            teaser="Why factories stopped keeping anything in stock.",
            read_time_min=5,
            blocks=_paragraph(JIT),
            topic_ids=(ECONOMICS,),
        )
    )

    for from_id, to_id, hook in (
        (CONTAINER, LOGISTICS, "The box was nothing without the cranes that danced it ashore."),
        (CONTAINER, MCLEAN, "One trucker looked at a ship and saw everything wrong."),
        (LOGISTICS, JIT, "Once boxes moved like clockwork, factories stopped keeping stock."),
        (MCLEAN, JIT, "His obsession with wasted motion became a manufacturing religion."),
        (JIT, CONTAINER, "Lean factories only work because the box never stops moving."),
    ):
        repo.upsert_connection(Connection(from_piece_id=from_id, to_piece_id=to_id, hook=hook))

    repo.set_daily_feature(feature_on, CONTAINER)
