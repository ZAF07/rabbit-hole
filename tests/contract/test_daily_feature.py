"""Contract: the Daily Feature is a date-keyed pointer to a Piece."""

import dataclasses
from datetime import date

import pytest

from content_graph.domain.blocks import BlockKind, ContentBlock
from content_graph.domain.errors import PieceNotFoundError
from content_graph.domain.piece import Piece
from content_graph.ports.repository import ContentGraphRepository


def _piece(piece_id: str, title: str) -> Piece:
    return Piece(
        id=piece_id,
        title=title,
        teaser=f"Teaser for {title}.",
        read_time_min=5,
        blocks=(ContentBlock(BlockKind.PARAGRAPH, {"text": f"Body of {title}."}),),
        run_id="run-7",
    )


def test_set_then_get_returns_the_pointed_to_piece(repo: ContentGraphRepository) -> None:
    repo.upsert_piece(_piece("piece-container", "The Shipping Container"))
    repo.set_daily_feature(date(2026, 7, 5), "piece-container")

    feature = repo.get_daily_feature(on=date(2026, 7, 5))

    assert feature is not None
    assert feature.id == "piece-container"
    assert feature.title == "The Shipping Container"
    assert len(feature.blocks) == 1


def test_reassigning_a_date_replaces_the_pointer(repo: ContentGraphRepository) -> None:
    repo.upsert_piece(_piece("piece-container", "The Shipping Container"))
    repo.upsert_piece(_piece("piece-suez", "The Day the Canal Closed"))
    repo.set_daily_feature(date(2026, 7, 5), "piece-container")
    repo.set_daily_feature(date(2026, 7, 5), "piece-suez")

    feature = repo.get_daily_feature(on=date(2026, 7, 5))

    assert feature is not None
    assert feature.id == "piece-suez"


def test_daily_feature_read_model_has_no_generation_only_fields(
    repo: ContentGraphRepository,
) -> None:
    repo.upsert_piece(_piece("piece-container", "The Shipping Container"))
    repo.set_daily_feature(date(2026, 7, 5), "piece-container")

    feature = repo.get_daily_feature(on=date(2026, 7, 5))

    assert feature is not None
    assert "run_id" not in {f.name for f in dataclasses.fields(feature)}


def test_get_daily_feature_returns_none_when_never_assigned(
    repo: ContentGraphRepository,
) -> None:
    assert repo.get_daily_feature(on=date(2026, 7, 5)) is None


def test_the_front_door_falls_back_to_the_most_recent_assignment(
    repo: ContentGraphRepository,
) -> None:
    repo.upsert_piece(_piece("piece-container", "The Shipping Container"))
    repo.set_daily_feature(date(2026, 7, 3), "piece-container")

    feature = repo.get_daily_feature(on=date(2026, 7, 5))

    assert feature is not None
    assert feature.id == "piece-container"


def test_future_assignments_are_not_surfaced_early(repo: ContentGraphRepository) -> None:
    repo.upsert_piece(_piece("piece-container", "The Shipping Container"))
    repo.set_daily_feature(date(2026, 7, 9), "piece-container")

    assert repo.get_daily_feature(on=date(2026, 7, 5)) is None


def test_pointing_at_a_missing_piece_is_rejected(repo: ContentGraphRepository) -> None:
    with pytest.raises(PieceNotFoundError):
        repo.set_daily_feature(date(2026, 7, 5), "piece-that-never-was")
