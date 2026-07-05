"""Unit tests for Content Block construction-time validation."""

import pytest

from content_graph.domain.blocks import TEXT_KINDS, VISUAL_KINDS, BlockKind, ContentBlock
from content_graph.domain.errors import (
    BlockValidationError,
    PieceValidationError,
    ReservedBlockKindError,
)
from content_graph.domain.piece import Piece


def test_vocabulary_reserves_visual_kinds_as_valid_enum_values() -> None:
    assert BlockKind("image") is BlockKind.IMAGE
    assert BlockKind("gif") is BlockKind.GIF
    assert BlockKind("diagram") is BlockKind.DIAGRAM
    assert frozenset(BlockKind) == TEXT_KINDS | VISUAL_KINDS


@pytest.mark.parametrize("kind", sorted(VISUAL_KINDS))
def test_visual_kinds_cannot_be_written_in_v1(kind: BlockKind) -> None:
    with pytest.raises(ReservedBlockKindError):
        ContentBlock(kind, {"src": "somewhere.png", "alt": "reserved"})


@pytest.mark.parametrize(
    "kind, payload",
    [
        (BlockKind.HEADING, {"level": 2}),
        (BlockKind.HEADING, {"text": "ok", "level": "two"}),
        (BlockKind.HEADING, {"text": "ok", "level": 0}),
        (BlockKind.PARAGRAPH, {}),
        (BlockKind.PARAGRAPH, {"text": "   "}),
        (BlockKind.PULL_QUOTE, {"attribution": "nobody"}),
        (BlockKind.PULL_QUOTE, {"text": "ok", "attribution": 7}),
        (BlockKind.STAT_CALLOUT, {"label": "no value"}),
        (BlockKind.STAT_CALLOUT, {"value": True, "label": "bool is not a stat"}),
        (BlockKind.STAT_CALLOUT, {"value": "90%"}),
    ],
)
def test_malformed_text_payloads_are_rejected(kind: BlockKind, payload: dict[str, object]) -> None:
    with pytest.raises(BlockValidationError):
        ContentBlock(kind, payload)


def test_well_formed_text_blocks_construct() -> None:
    ContentBlock(BlockKind.HEADING, {"text": "A heading", "level": 2})
    ContentBlock(BlockKind.PARAGRAPH, {"text": "A paragraph."})
    ContentBlock(BlockKind.PULL_QUOTE, {"text": "Quotable."})
    ContentBlock(BlockKind.PULL_QUOTE, {"text": "Quotable.", "attribution": "Someone"})
    ContentBlock(BlockKind.STAT_CALLOUT, {"value": 400, "label": "ships"})


@pytest.mark.parametrize(
    "overrides",
    [
        {"id": ""},
        {"title": "  "},
        {"teaser": ""},
        {"read_time_min": 0},
        {"read_time_min": True},
    ],
)
def test_piece_scalar_validation(overrides: dict[str, object]) -> None:
    fields: dict[str, object] = {
        "id": "piece-x",
        "title": "Title",
        "teaser": "Teaser",
        "read_time_min": 5,
    }
    fields.update(overrides)
    with pytest.raises(PieceValidationError):
        Piece(**fields)  # type: ignore[arg-type]
