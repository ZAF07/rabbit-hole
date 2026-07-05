"""Issue 04 — the Tapestry: the reader's Personal Knowledge Graph."""

from tests.consumption.fixture_constellation import (
    CONTAINER,
    JIT,
    LOGISTICS,
    MCLEAN,
)

from consumption.application.reader import ReaderService


def _wander(reader: ReaderService, user_id: str) -> None:
    """A small journey: container -> logistics -> jit, backtrack, container -> mclean."""
    reader.enter_piece(user_id, CONTAINER)
    reader.pull_connection(user_id, CONTAINER, LOGISTICS)
    reader.pull_connection(user_id, LOGISTICS, JIT)
    reader.backtrack(user_id)
    reader.backtrack(user_id)
    reader.pull_connection(user_id, CONTAINER, MCLEAN)


def test_tapestry_is_the_deduped_union_of_nodes_and_pulled_edges(
    reader: ReaderService, user_id: str
) -> None:
    _wander(reader, user_id)

    tapestry = reader.get_personal_knowledge_graph(user_id)

    assert [node.piece_id for node in tapestry.nodes] == [CONTAINER, LOGISTICS, JIT, MCLEAN]
    assert [(edge.from_piece_id, edge.to_piece_id) for edge in tapestry.edges] == [
        (CONTAINER, LOGISTICS),
        (LOGISTICS, JIT),
        (CONTAINER, MCLEAN),
    ]


def test_tapestry_nodes_carry_topics_for_colouring_and_clustering(
    reader: ReaderService, user_id: str
) -> None:
    _wander(reader, user_id)

    tapestry = reader.get_personal_knowledge_graph(user_id)

    by_id = {node.piece_id: node for node in tapestry.nodes}
    assert {topic.slug for topic in by_id[CONTAINER].topics} == {"economics", "history"}
    assert {topic.slug for topic in by_id[LOGISTICS].topics} == {"technology"}


def test_tapestry_is_seeded_by_the_first_daily_feature(reader: ReaderService, user_id: str) -> None:
    feature = reader.get_daily_feature()
    assert feature is not None

    reader.enter_piece(user_id, feature.piece.id)  # first-run seed
    tapestry = reader.get_personal_knowledge_graph(user_id)

    assert [node.piece_id for node in tapestry.nodes] == [feature.piece.id]


def test_tapping_a_node_re_enters_that_piece_and_permits_a_different_fork(
    reader: ReaderService, user_id: str
) -> None:
    _wander(reader, user_id)
    tapestry = reader.get_personal_knowledge_graph(user_id)
    logistics_node = next(node for node in tapestry.nodes if node.piece_id == LOGISTICS)

    revisited = reader.enter_piece(user_id, logistics_node.piece_id)  # tap the node
    onward = reader.pull_connection(user_id, LOGISTICS, JIT)  # pull a fork from it

    assert revisited.piece.id == LOGISTICS
    assert onward.piece.id == JIT


def test_re_reading_a_node_does_not_add_a_duplicate_or_inflate_the_graph(
    reader: ReaderService, user_id: str
) -> None:
    _wander(reader, user_id)
    before = reader.get_personal_knowledge_graph(user_id)

    reader.enter_piece(user_id, LOGISTICS)  # re-read covered ground
    reader.read_piece(CONTAINER)  # a pure re-read

    after = reader.get_personal_knowledge_graph(user_id)
    assert [node.piece_id for node in after.nodes] == [node.piece_id for node in before.nodes]
    assert len(after.edges) == len(before.edges)


def test_tapestry_is_empty_before_the_journey_begins(reader: ReaderService, user_id: str) -> None:
    tapestry = reader.get_personal_knowledge_graph(user_id)

    assert tapestry.nodes == ()
    assert tapestry.edges == ()
