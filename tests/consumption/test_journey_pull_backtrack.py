"""Issue 02 — identity + linear Session path: pull, backtrack, depth."""

import pytest
from tests.consumption.fixture_constellation import (
    CONTAINER,
    JIT,
    LOGISTICS,
    MCLEAN,
)

from consumption.application.reader import ReaderService
from consumption.domain.errors import (
    CannotBacktrackError,
    FreeRoamError,
    NoJourneyError,
    NotCurrentPieceError,
    UnknownConnectionError,
    UnknownUserError,
)


def test_pull_connection_advances_to_the_destination_and_appends_it(
    reader: ReaderService, user_id: str
) -> None:
    reader.enter_piece(user_id, CONTAINER)

    reading = reader.pull_connection(user_id, CONTAINER, LOGISTICS)

    assert reading.piece.id == LOGISTICS
    journey = reader.get_journey(user_id)
    assert journey is not None
    assert journey.current_piece_id == LOGISTICS
    assert journey.stack == (CONTAINER, LOGISTICS)


def test_backtrack_pops_to_the_prior_piece_and_permits_a_different_fork(
    reader: ReaderService, user_id: str
) -> None:
    reader.enter_piece(user_id, CONTAINER)
    reader.pull_connection(user_id, CONTAINER, LOGISTICS)

    back = reader.backtrack(user_id)

    assert back.piece.id == CONTAINER
    other = reader.pull_connection(user_id, CONTAINER, MCLEAN)
    assert other.piece.id == MCLEAN
    journey = reader.get_journey(user_id)
    assert journey is not None
    assert journey.stack == (CONTAINER, MCLEAN)


def test_backtracking_behaves_like_a_stack_not_a_teleport(
    reader: ReaderService, user_id: str
) -> None:
    reader.enter_piece(user_id, CONTAINER)
    reader.pull_connection(user_id, CONTAINER, LOGISTICS)
    reader.pull_connection(user_id, LOGISTICS, JIT)

    assert reader.backtrack(user_id).piece.id == LOGISTICS
    assert reader.backtrack(user_id).piece.id == CONTAINER


def test_backtracking_past_the_root_is_refused(reader: ReaderService, user_id: str) -> None:
    reader.enter_piece(user_id, CONTAINER)

    with pytest.raises(CannotBacktrackError):
        reader.backtrack(user_id)


def test_depth_counts_distinct_pieces_and_a_new_fork_raises_it(
    reader: ReaderService, user_id: str
) -> None:
    reader.enter_piece(user_id, CONTAINER)
    assert reader.get_journey(user_id).depth == 1  # type: ignore[union-attr]

    reader.pull_connection(user_id, CONTAINER, LOGISTICS)
    assert reader.get_journey(user_id).depth == 2  # type: ignore[union-attr]

    reader.backtrack(user_id)
    assert reader.get_journey(user_id).depth == 2  # backtracking is not new ground

    reader.pull_connection(user_id, CONTAINER, MCLEAN)
    assert reader.get_journey(user_id).depth == 3  # a new fork covers new ground


def test_re_entering_a_visited_piece_does_not_inflate_depth(
    reader: ReaderService, user_id: str
) -> None:
    reader.enter_piece(user_id, CONTAINER)
    reader.pull_connection(user_id, CONTAINER, LOGISTICS)
    reader.pull_connection(user_id, LOGISTICS, JIT)
    depth_before = reader.get_journey(user_id).depth  # type: ignore[union-attr]

    reader.enter_piece(user_id, CONTAINER)  # re-enter covered ground

    assert reader.get_journey(user_id).depth == depth_before  # type: ignore[union-attr]


def test_pulling_a_connection_to_an_already_visited_piece_does_not_inflate_depth(
    reader: ReaderService, user_id: str
) -> None:
    reader.enter_piece(user_id, CONTAINER)
    reader.pull_connection(user_id, CONTAINER, LOGISTICS)
    reader.pull_connection(user_id, LOGISTICS, JIT)
    depth_before = reader.get_journey(user_id).depth  # type: ignore[union-attr]

    reader.pull_connection(user_id, JIT, CONTAINER)  # loops back to a visited node

    assert reader.get_journey(user_id).depth == depth_before  # type: ignore[union-attr]


def test_pull_requires_the_reader_to_stand_on_the_origin(
    reader: ReaderService, user_id: str
) -> None:
    reader.enter_piece(user_id, CONTAINER)
    reader.pull_connection(user_id, CONTAINER, LOGISTICS)

    with pytest.raises(NotCurrentPieceError):
        reader.pull_connection(user_id, CONTAINER, MCLEAN)


def test_pull_refuses_a_connection_that_does_not_exist(reader: ReaderService, user_id: str) -> None:
    reader.enter_piece(user_id, CONTAINER)

    with pytest.raises(UnknownConnectionError):
        reader.pull_connection(user_id, CONTAINER, JIT)  # no direct container -> jit edge


def test_entering_an_unvisited_non_feature_piece_is_refused_as_free_roam(
    reader: ReaderService, user_id: str
) -> None:
    with pytest.raises(FreeRoamError):
        reader.enter_piece(user_id, JIT)  # not the Daily Feature, not yet visited


def test_navigation_requires_a_registered_identity(reader: ReaderService) -> None:
    with pytest.raises(UnknownUserError):
        reader.enter_piece("user-nobody", CONTAINER)


def test_pull_before_entering_is_refused(reader: ReaderService, user_id: str) -> None:
    with pytest.raises(NoJourneyError):
        reader.pull_connection(user_id, CONTAINER, LOGISTICS)


def test_the_path_is_persisted_per_user(reader: ReaderService, user_id: str) -> None:
    reader.enter_piece(user_id, CONTAINER)
    reader.pull_connection(user_id, CONTAINER, LOGISTICS)

    other = "user-grace"
    reader.create_user(other)
    reader.enter_piece(other, CONTAINER)

    ada = reader.get_journey(user_id)
    grace = reader.get_journey(other)
    assert ada is not None and ada.stack == (CONTAINER, LOGISTICS)
    assert grace is not None and grace.stack == (CONTAINER,)
