"""Contract: the V1 seed taxonomy loads through the write surface, idempotently."""

from pathlib import Path

from content_graph.domain.blocks import BlockKind, ContentBlock
from content_graph.domain.piece import Piece
from content_graph.ports.repository import ContentGraphRepository
from content_graph.seed import load_seed_taxonomy

TAXONOMY_MD = (Path(__file__).parents[2] / "docs" / "taxonomy.md").read_text(encoding="utf-8")


def _probe_piece(topic_ids: tuple[str, ...]) -> Piece:
    return Piece(
        id="piece-probe",
        title="Probe",
        teaser="A probe piece for taxonomy assertions.",
        read_time_min=3,
        blocks=(ContentBlock(BlockKind.PARAGRAPH, {"text": "Probe."}),),
        topic_ids=topic_ids,
    )


def test_seed_taxonomy_loads_and_is_idempotent(repo: ContentGraphRepository) -> None:
    first = load_seed_taxonomy(repo, TAXONOMY_MD)
    second = load_seed_taxonomy(repo, TAXONOMY_MD)

    assert {topic.id for topic in first} == {topic.id for topic in second}

    repo.upsert_piece(
        _probe_piece(("behavioral-economics", "cyber-conflict", "engineering-and-infrastructure"))
    )
    by_id = {topic.id: topic for topic in repo.get_topics_for(["piece-probe"])["piece-probe"]}

    behavioral = by_id["behavioral-economics"]
    assert set(behavioral.parent_ids) == {"economics-and-markets", "psychology-and-the-mind"}

    cyber = by_id["cyber-conflict"]
    assert set(cyber.parent_ids) == {"technology-and-computing", "warfare-and-strategy"}

    assert by_id["engineering-and-infrastructure"].parent_ids == ()
