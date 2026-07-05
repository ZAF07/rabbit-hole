"""Contract tests for the generation-side read surface (Architect dedup, publish)."""

from content_graph.domain.piece import Piece
from content_graph.domain.topic import Topic


def _seed(repo):
    repo.upsert_topic(Topic(id="ships", slug="ships", title="Ships"))
    repo.upsert_topic(Topic(id="trade", slug="trade", title="Trade"))
    repo.set_topic_parents("ships", ["trade"])
    repo.upsert_piece(
        Piece(id="b", title="B title", teaser="B teaser", read_time_min=3, topic_ids=("ships",))
    )
    repo.upsert_piece(
        Piece(id="a", title="A title", teaser="A teaser", read_time_min=4, topic_ids=("trade",))
    )


def test_get_topic_returns_read_model_with_parents(repo):
    _seed(repo)
    topic = repo.get_topic("ships")
    assert topic is not None
    assert topic.slug == "ships"
    assert topic.parent_ids == ("trade",)


def test_get_topic_returns_none_for_unknown(repo):
    assert repo.get_topic("nope") is None


def test_list_piece_summaries_lists_all_ordered_by_id(repo):
    _seed(repo)
    summaries = repo.list_piece_summaries()
    assert [summary.id for summary in summaries] == ["a", "b"]
    assert summaries[0].title == "A title"
    assert summaries[1].topics[0].slug == "ships"


def test_list_piece_summaries_empty_store(repo):
    assert repo.list_piece_summaries() == ()
