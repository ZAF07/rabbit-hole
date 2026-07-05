"""Issue 01 — the walking skeleton: Daily Feature -> Read Piece -> previews."""

from datetime import date

from tests.consumption.fixture_constellation import (
    CONTAINER,
    LOGISTICS,
    MCLEAN,
    TODAY,
)

from consumption.application.reader import ReaderService


def test_get_daily_feature_returns_entry_piece_with_its_teaser(reader: ReaderService) -> None:
    feature = reader.get_daily_feature(TODAY)

    assert feature is not None
    assert feature.piece.id == CONTAINER
    assert feature.piece.teaser == "How a steel box rewired the world economy."
    assert feature.piece.read_time_min == 6
    assert {topic.slug for topic in feature.piece.topics} == {"economics", "history"}


def test_daily_feature_lets_the_reader_peek_at_onward_connections(reader: ReaderService) -> None:
    feature = reader.get_daily_feature(TODAY)

    assert feature is not None
    destinations = [preview.to_piece_id for preview in feature.connections]
    assert destinations == [LOGISTICS, MCLEAN]
    peek = feature.connections[0]
    assert peek.hook == "The box was nothing without the cranes that danced it ashore."
    assert peek.to_title == "The Ballet of the Cranes"
    assert {topic.slug for topic in peek.to_topics} == {"technology"}


def test_daily_feature_inherits_the_last_assigned_on_a_missed_day(reader: ReaderService) -> None:
    later = reader.get_daily_feature(date(2026, 7, 20))

    assert later is not None
    assert later.piece.id == CONTAINER


def test_read_piece_returns_ordered_blocks_and_connection_previews(reader: ReaderService) -> None:
    reading = reader.read_piece(CONTAINER)

    assert reading is not None
    assert [block.kind.value for block in reading.piece.blocks] == [
        "heading",
        "paragraph",
        "pull-quote",
        "stat-callout",
        "paragraph",
    ]
    assert [preview.to_piece_id for preview in reading.connections] == [LOGISTICS, MCLEAN]


def test_read_piece_onward_previews_carry_the_connection_hook(reader: ReaderService) -> None:
    reading = reader.read_piece(CONTAINER)

    assert reading is not None
    hooks = {preview.to_piece_id: preview.hook for preview in reading.connections}
    assert hooks[MCLEAN] == "One trucker looked at a ship and saw everything wrong."


def test_entry_teaser_and_onward_hook_are_never_conflated(reader: ReaderService) -> None:
    feature = reader.get_daily_feature(TODAY)

    assert feature is not None
    entry_lure = feature.piece.teaser
    onward_lures = {preview.hook for preview in feature.connections}
    assert entry_lure not in onward_lures


def test_read_piece_returns_none_for_unknown_piece(reader: ReaderService) -> None:
    assert reader.read_piece("piece-that-never-was") is None


def test_get_daily_feature_returns_none_before_any_assignment(reader: ReaderService) -> None:
    assert reader.get_daily_feature(date(2000, 1, 1)) is None
