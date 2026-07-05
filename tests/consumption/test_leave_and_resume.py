"""Issue 03 — leave & resume: Session boundary, resumable path, daily hook."""

from datetime import UTC, datetime, timedelta

from tests.consumption.clock import MutableClock
from tests.consumption.fixture_constellation import CONTAINER, LOGISTICS, TODAY

from consumption.application.reader import ReaderService
from consumption.domain.session import INACTIVITY_TIMEOUT, Session
from consumption.ports.session_repository import SessionRepository

_START = datetime(2026, 7, 5, 9, 0, tzinfo=UTC)


def _session(**overrides: object) -> Session:
    fields: dict[str, object] = {
        "id": "s",
        "user_id": "user-ada",
        "started_at": _START,
        "last_activity_at": _START,
    }
    fields.update(overrides)
    return Session(**fields)  # type: ignore[arg-type]


def test_session_expires_after_the_inactivity_budget() -> None:
    session = _session()

    assert not session.is_expired(_START + INACTIVITY_TIMEOUT - timedelta(minutes=1))
    assert session.is_expired(_START + INACTIVITY_TIMEOUT)


def test_session_is_expired_once_explicitly_ended() -> None:
    session = _session(ended_at=_START)

    assert session.is_expired(_START)  # a closed window is over regardless of the clock


def test_resume_restores_current_piece_and_backtrack_stack(
    reader: ReaderService, user_id: str
) -> None:
    reader.enter_piece(user_id, CONTAINER)
    reader.pull_connection(user_id, CONTAINER, LOGISTICS)

    resumed = reader.resume(user_id)

    assert resumed is not None
    assert resumed.reading.piece.id == LOGISTICS
    assert resumed.stack == (CONTAINER, LOGISTICS)


def test_resume_after_the_gap_starts_a_new_session_continuing_the_same_path(
    reader: ReaderService,
    sessions: SessionRepository,
    clock: MutableClock,
    user_id: str,
) -> None:
    reader.enter_piece(user_id, CONTAINER)
    reader.pull_connection(user_id, CONTAINER, LOGISTICS)
    before = sessions.get_current_session(user_id)
    assert before is not None

    clock.advance(INACTIVITY_TIMEOUT + timedelta(minutes=1))
    resumed = reader.resume(user_id)

    after = sessions.get_current_session(user_id)
    assert after is not None
    assert after.id != before.id  # a new analytics window
    assert after.ended_at is None
    assert resumed is not None
    assert resumed.session_id == after.id
    assert resumed.stack == (CONTAINER, LOGISTICS)  # same durable path


def test_resume_within_the_window_keeps_the_same_session(
    reader: ReaderService,
    sessions: SessionRepository,
    clock: MutableClock,
    user_id: str,
) -> None:
    reader.enter_piece(user_id, CONTAINER)
    before = sessions.get_current_session(user_id)
    assert before is not None

    clock.advance(timedelta(minutes=5))
    reader.resume(user_id)

    after = sessions.get_current_session(user_id)
    assert after is not None
    assert after.id == before.id


def test_app_close_ends_the_session_and_the_next_resume_opens_a_new_one(
    reader: ReaderService,
    sessions: SessionRepository,
    clock: MutableClock,
    user_id: str,
) -> None:
    reader.enter_piece(user_id, CONTAINER)
    before = sessions.get_current_session(user_id)
    assert before is not None

    reader.close(user_id)
    closed = sessions.get_current_session(user_id)
    assert closed is not None and closed.ended_at is not None

    clock.advance(timedelta(minutes=2))
    resumed = reader.resume(user_id)

    after = sessions.get_current_session(user_id)
    assert after is not None
    assert after.id != before.id
    assert after.ended_at is None
    assert resumed is not None and resumed.stack == (CONTAINER,)


def test_the_daily_feature_is_still_served_when_a_resumable_thread_exists(
    reader: ReaderService, user_id: str
) -> None:
    reader.enter_piece(user_id, CONTAINER)
    reader.pull_connection(user_id, CONTAINER, LOGISTICS)

    feature = reader.get_daily_feature(TODAY)
    resumed = reader.resume(user_id)

    assert feature is not None and feature.piece.id == CONTAINER  # heartbeat still greets
    assert resumed is not None and resumed.reading.piece.id == LOGISTICS  # and a way back in


def test_resume_returns_none_when_there_is_no_path(reader: ReaderService, user_id: str) -> None:
    assert reader.resume(user_id) is None


def test_daily_notification_teases_the_real_hook_without_bait_and_switch(
    reader: ReaderService,
) -> None:
    note = reader.daily_notification(TODAY)
    feature = reader.get_daily_feature(TODAY)

    assert note is not None and feature is not None
    assert note.piece_id == feature.piece.id  # points at the Piece it opens
    assert note.teaser == feature.piece.teaser  # the same real hook, not a substitute
