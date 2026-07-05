"""Contract: a Piece round-trips through the port with its body intact."""

import dataclasses

from content_graph.domain.blocks import BlockKind, ContentBlock
from content_graph.domain.piece import Piece
from content_graph.ports.repository import ContentGraphRepository


def _mixed_text_body() -> tuple[ContentBlock, ...]:
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


def _shipping_piece(**overrides: object) -> Piece:
    fields: dict[str, object] = {
        "id": "piece-shipping-container",
        "title": "The Shipping Container",
        "teaser": "How a steel box rewired the world economy.",
        "read_time_min": 5,
        "blocks": _mixed_text_body(),
    }
    fields.update(overrides)
    return Piece(**fields)  # type: ignore[arg-type]


def test_piece_round_trips_with_block_order_and_kinds_preserved(
    repo: ContentGraphRepository,
) -> None:
    piece = _shipping_piece()

    repo.upsert_piece(piece)
    read = repo.get_piece(piece.id)

    assert read is not None
    assert read.id == piece.id
    assert read.title == piece.title
    assert read.teaser == piece.teaser
    assert read.read_time_min == piece.read_time_min
    assert [block.kind for block in read.blocks] == [block.kind for block in piece.blocks]
    assert [dict(block.payload) for block in read.blocks] == [
        dict(block.payload) for block in piece.blocks
    ]


def test_upsert_piece_is_idempotent_by_identity(repo: ContentGraphRepository) -> None:
    repo.upsert_piece(_shipping_piece())
    repo.upsert_piece(_shipping_piece())

    read = repo.get_piece("piece-shipping-container")

    assert read is not None
    assert len(read.blocks) == 5


def test_reupserting_replaces_fields_and_body(repo: ContentGraphRepository) -> None:
    repo.upsert_piece(_shipping_piece())
    revised = _shipping_piece(
        title="The Box",
        blocks=(ContentBlock(BlockKind.PARAGRAPH, {"text": "A shorter cut."}),),
    )

    repo.upsert_piece(revised)
    read = repo.get_piece("piece-shipping-container")

    assert read is not None
    assert read.title == "The Box"
    assert len(read.blocks) == 1


def test_read_model_excludes_generation_only_fields(repo: ContentGraphRepository) -> None:
    repo.upsert_piece(_shipping_piece(run_id="run-42"))

    read = repo.get_piece("piece-shipping-container")

    assert read is not None
    field_names = {f.name for f in dataclasses.fields(read)}
    assert "run_id" not in field_names
    assert not hasattr(read, "run_id")


def test_get_piece_returns_none_for_unknown_id(repo: ContentGraphRepository) -> None:
    assert repo.get_piece("piece-that-never-was") is None
