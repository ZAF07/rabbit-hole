"""Contract: piece summaries serve entry surfaces — teaser and Topics, no body."""

import dataclasses

from content_graph.domain.blocks import BlockKind, ContentBlock
from content_graph.domain.piece import Piece
from content_graph.domain.topic import Topic
from content_graph.ports.repository import ContentGraphRepository


def _piece(piece_id: str, title: str, topic_ids: tuple[str, ...] = ()) -> Piece:
    return Piece(
        id=piece_id,
        title=title,
        teaser=f"Teaser for {title}.",
        read_time_min=6,
        blocks=(ContentBlock(BlockKind.PARAGRAPH, {"text": f"Body of {title}."}),),
        topic_ids=topic_ids,
        run_id="run-9",
    )


def test_summaries_carry_teaser_and_topics_but_no_body_or_provenance(
    repo: ContentGraphRepository,
) -> None:
    repo.upsert_topic(Topic(id="logistics", slug="logistics", title="Logistics & Supply Chains"))
    repo.upsert_piece(_piece("piece-container", "The Shipping Container", ("logistics",)))
    repo.upsert_piece(_piece("piece-suez", "The Day the Canal Closed"))

    summaries = repo.get_piece_summaries(["piece-container", "piece-suez", "piece-that-never-was"])

    assert set(summaries) == {"piece-container", "piece-suez"}
    container = summaries["piece-container"]
    assert container.title == "The Shipping Container"
    assert container.teaser == "Teaser for The Shipping Container."
    assert container.read_time_min == 6
    assert [topic.id for topic in container.topics] == ["logistics"]
    field_names = {f.name for f in dataclasses.fields(container)}
    assert "run_id" not in field_names
    assert "blocks" not in field_names
