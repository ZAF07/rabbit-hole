"""Contract: Connections are directed edges carrying their own per-origin hook."""

import pytest

from content_graph.domain.blocks import BlockKind, ContentBlock
from content_graph.domain.connection import Connection
from content_graph.domain.errors import PieceNotFoundError
from content_graph.domain.piece import Piece
from content_graph.domain.topic import Topic
from content_graph.ports.repository import ContentGraphRepository


def _piece(piece_id: str, title: str, topic_ids: tuple[str, ...] = ()) -> Piece:
    return Piece(
        id=piece_id,
        title=title,
        teaser=f"Teaser for {title}.",
        read_time_min=5,
        blocks=(ContentBlock(BlockKind.PARAGRAPH, {"text": f"Body of {title}."}),),
        topic_ids=topic_ids,
    )


def _seed_pieces(repo: ContentGraphRepository) -> None:
    repo.upsert_topic(Topic(id="logistics", slug="logistics", title="Logistics & Supply Chains"))
    repo.upsert_topic(Topic(id="game-theory", slug="game-theory", title="Game Theory"))
    repo.upsert_piece(_piece("piece-container", "The Shipping Container", ("logistics",)))
    repo.upsert_piece(_piece("piece-suez", "The Day the Canal Closed", ("logistics",)))
    repo.upsert_piece(
        _piece("piece-standards", "Why Standards Win Wars", ("logistics", "game-theory"))
    )


def test_connection_round_trips_with_hook_and_destination_join(
    repo: ContentGraphRepository,
) -> None:
    _seed_pieces(repo)
    repo.upsert_connection(
        Connection(
            from_piece_id="piece-container",
            to_piece_id="piece-standards",
            hook="The box only worked once everyone agreed how big it was.",
        )
    )

    (preview,) = repo.get_connections_from("piece-container")

    assert preview.from_piece_id == "piece-container"
    assert preview.to_piece_id == "piece-standards"
    assert preview.hook == "The box only worked once everyone agreed how big it was."
    assert preview.to_title == "Why Standards Win Wars"
    assert {topic.id for topic in preview.to_topics} == {"logistics", "game-theory"}


def test_connection_to_missing_destination_is_rejected(repo: ContentGraphRepository) -> None:
    _seed_pieces(repo)
    with pytest.raises(PieceNotFoundError):
        repo.upsert_connection(
            Connection(
                from_piece_id="piece-container",
                to_piece_id="piece-that-never-was",
                hook="A dead link.",
            )
        )


def test_connection_from_missing_origin_is_rejected(repo: ContentGraphRepository) -> None:
    _seed_pieces(repo)
    with pytest.raises(PieceNotFoundError):
        repo.upsert_connection(
            Connection(
                from_piece_id="piece-that-never-was",
                to_piece_id="piece-container",
                hook="A dead origin.",
            )
        )


def test_same_destination_carries_a_different_hook_per_origin(
    repo: ContentGraphRepository,
) -> None:
    _seed_pieces(repo)
    repo.upsert_connection(
        Connection(
            from_piece_id="piece-container",
            to_piece_id="piece-standards",
            hook="The box only worked once everyone agreed how big it was.",
        )
    )
    repo.upsert_connection(
        Connection(
            from_piece_id="piece-suez",
            to_piece_id="piece-standards",
            hook="Blockades end when everyone plays by the same rules.",
        )
    )

    (from_container,) = repo.get_connections_from("piece-container")
    (from_suez,) = repo.get_connections_from("piece-suez")

    assert from_container.to_piece_id == from_suez.to_piece_id
    assert from_container.hook != from_suez.hook


def test_inbound_and_outbound_connections_are_queryable(repo: ContentGraphRepository) -> None:
    _seed_pieces(repo)
    repo.upsert_connection(
        Connection("piece-container", "piece-standards", "Agree on the box, win the port.")
    )
    repo.upsert_connection(Connection("piece-suez", "piece-standards", "Rules outlast blockades."))
    repo.upsert_connection(
        Connection("piece-standards", "piece-container", "Standards need something to measure.")
    )

    inbound = repo.get_connections_to("piece-standards")
    outbound = repo.get_connections_from("piece-standards")

    assert {conn.from_piece_id for conn in inbound} == {"piece-container", "piece-suez"}
    assert [conn.to_piece_id for conn in outbound] == ["piece-container"]


def test_upsert_connection_is_idempotent_by_endpoints(repo: ContentGraphRepository) -> None:
    _seed_pieces(repo)
    repo.upsert_connection(Connection("piece-container", "piece-suez", "First hook."))
    repo.upsert_connection(Connection("piece-container", "piece-suez", "Sharper hook."))

    previews = repo.get_connections_from("piece-container")

    assert len(previews) == 1
    assert previews[0].hook == "Sharper hook."


def test_pieces_without_connections_have_empty_edges(repo: ContentGraphRepository) -> None:
    _seed_pieces(repo)

    assert repo.get_connections_from("piece-container") == ()
    assert repo.get_connections_to("piece-container") == ()
