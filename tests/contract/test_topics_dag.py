"""Contract: Topics form a multi-parent DAG; a Piece belongs to many Topics."""

import pytest

from content_graph.domain.blocks import BlockKind, ContentBlock
from content_graph.domain.errors import TopicNotFoundError
from content_graph.domain.piece import Piece
from content_graph.domain.topic import Topic
from content_graph.ports.repository import ContentGraphRepository


def _piece(piece_id: str = "piece-nudge", topic_ids: tuple[str, ...] = ()) -> Piece:
    return Piece(
        id=piece_id,
        title="The Nudge",
        teaser="Why defaults decide more than you do.",
        read_time_min=4,
        blocks=(ContentBlock(BlockKind.PARAGRAPH, {"text": "Choice architecture is destiny."}),),
        topic_ids=topic_ids,
    )


def _seed_dag(repo: ContentGraphRepository) -> None:
    repo.upsert_topic(Topic(id="economics", slug="economics", title="Economics & Markets"))
    repo.upsert_topic(Topic(id="psychology", slug="psychology", title="Psychology & the Mind"))
    repo.upsert_topic(
        Topic(id="behavioral-econ", slug="behavioral-econ", title="Behavioral Economics")
    )
    repo.set_topic_parents("behavioral-econ", ["economics", "psychology"])


def test_topic_with_several_parents_round_trips(repo: ContentGraphRepository) -> None:
    _seed_dag(repo)
    repo.upsert_piece(_piece(topic_ids=("behavioral-econ",)))

    topics = repo.get_topics_for(["piece-nudge"])

    (behavioral,) = topics["piece-nudge"]
    assert behavioral.id == "behavioral-econ"
    assert behavioral.title == "Behavioral Economics"
    assert set(behavioral.parent_ids) == {"economics", "psychology"}


def test_piece_with_several_topics_round_trips(repo: ContentGraphRepository) -> None:
    _seed_dag(repo)
    repo.upsert_piece(_piece(topic_ids=("behavioral-econ", "economics", "psychology")))

    read = repo.get_piece("piece-nudge")
    topics = repo.get_topics_for(["piece-nudge"])

    assert read is not None
    assert {topic.id for topic in read.topics} == {"behavioral-econ", "economics", "psychology"}
    assert {topic.id for topic in topics["piece-nudge"]} == {
        "behavioral-econ",
        "economics",
        "psychology",
    }


def test_topic_upserts_and_parent_sets_are_idempotent(repo: ContentGraphRepository) -> None:
    _seed_dag(repo)
    _seed_dag(repo)
    repo.upsert_piece(_piece(topic_ids=("behavioral-econ",)))
    repo.upsert_piece(_piece(topic_ids=("behavioral-econ",)))

    topics = repo.get_topics_for(["piece-nudge"])

    (behavioral,) = topics["piece-nudge"]
    assert len(behavioral.parent_ids) == 2


def test_upsert_topic_updates_title_by_identity(repo: ContentGraphRepository) -> None:
    _seed_dag(repo)
    repo.upsert_topic(Topic(id="economics", slug="economics", title="Economics"))
    repo.upsert_piece(_piece(topic_ids=("economics",)))

    (economics,) = repo.get_topics_for(["piece-nudge"])["piece-nudge"]

    assert economics.title == "Economics"


def test_set_topic_parents_replaces_the_whole_set(repo: ContentGraphRepository) -> None:
    _seed_dag(repo)
    repo.set_topic_parents("behavioral-econ", ["economics"])
    repo.upsert_piece(_piece(topic_ids=("behavioral-econ",)))

    (behavioral,) = repo.get_topics_for(["piece-nudge"])["piece-nudge"]

    assert behavioral.parent_ids == ("economics",)


def test_tagging_a_piece_with_a_missing_topic_is_rejected(repo: ContentGraphRepository) -> None:
    with pytest.raises(TopicNotFoundError):
        repo.upsert_piece(_piece(topic_ids=("ghost-topic",)))


def test_setting_parents_on_or_to_a_missing_topic_is_rejected(
    repo: ContentGraphRepository,
) -> None:
    _seed_dag(repo)
    with pytest.raises(TopicNotFoundError):
        repo.set_topic_parents("ghost-topic", ["economics"])
    with pytest.raises(TopicNotFoundError):
        repo.set_topic_parents("economics", ["ghost-topic"])


def test_get_topics_for_covers_untagged_and_unknown_pieces(repo: ContentGraphRepository) -> None:
    _seed_dag(repo)
    repo.upsert_piece(_piece(topic_ids=()))

    topics = repo.get_topics_for(["piece-nudge", "piece-that-never-was"])

    assert topics["piece-nudge"] == ()
    assert "piece-that-never-was" not in topics
