"""The reader application service — the use-case boundary the loop runs over.

Every reader use-case is a method here, driven over the Content Graph's read
surface and the reader's own identity and path stores. The service speaks
internal vocabulary only and never imports the presentation bundle (ADR 0001).
It reads only Pieces and Connections; nothing generation-only crosses into it
(ADR 0006).
"""

from collections.abc import Callable
from dataclasses import replace
from datetime import date
from uuid import uuid4

from consumption.domain.errors import (
    FreeRoamError,
    NoJourneyError,
    NotCurrentPieceError,
    UnknownConnectionError,
    UnknownUserError,
)
from consumption.domain.identity import User
from consumption.domain.journey import Journey
from consumption.domain.read_models import (
    DailyFeatureView,
    DailyNotification,
    JourneyView,
    PersonalKnowledgeGraph,
    PersonalKnowledgeGraphEdge,
    PersonalKnowledgeGraphNode,
    ReadingView,
    ResumeView,
    summarize,
)
from consumption.domain.session import Session
from consumption.ports.clock import Clock
from consumption.ports.session_repository import SessionRepository
from consumption.ports.user_repository import UserRepository
from content_graph.ports.repository import ContentGraphRepository


class ReaderService:
    """The reader's use-cases over the Content Graph and the reader's own stores."""

    def __init__(
        self,
        content: ContentGraphRepository,
        sessions: SessionRepository,
        users: UserRepository,
        clock: Clock,
        id_factory: Callable[[], str] | None = None,
    ) -> None:
        """Wire the service to the Content Graph read surface and reader stores.

        Args:
            content: The Content Graph repository; only its read methods are
                ever called from consumption.
            sessions: The durable path store.
            users: The identity store.
            clock: The source of the current instant (drives the Session
                boundary).
            id_factory: Mints new analytics-Session ids; defaults to random
                UUIDs. Injectable so tests get deterministic ids.
        """
        self._content = content
        self._sessions = sessions
        self._users = users
        self._clock = clock
        self._new_session_id = id_factory or (lambda: uuid4().hex)

    def get_daily_feature(self, on: date | None = None) -> DailyFeatureView | None:
        """Return the day's featured Piece as an entry surface with a peek onward.

        The current Daily Feature is the most recently assigned Piece on or
        before ``on`` (the front door is never blank on a missed day).

        Args:
            on: The date to resolve for; defaults to today.

        Returns:
            The front-door view — the featured Piece's teaser-led summary plus
            its onward Connection previews — or None if none has been assigned.
        """
        piece = self._content.get_daily_feature(on)
        if piece is None:
            return None
        return DailyFeatureView(
            piece=summarize(piece),
            connections=self._content.get_connections_from(piece.id),
        )

    def read_piece(self, piece_id: str) -> ReadingView | None:
        """Open a Piece for reading: its full ordered body and where it Connects.

        A pure render with no journey side effect — used for the walking
        skeleton and to preview a Piece without recording it.

        Args:
            piece_id: The Piece to read.

        Returns:
            The reading view, or None if no such Piece exists.
        """
        return self._reading_view(piece_id)

    def create_user(self, user_id: str) -> User:
        """Register a reader identity; idempotent by id.

        Args:
            user_id: The identity to create.

        Returns:
            The persisted User.
        """
        user = User(id=user_id)
        self._users.add(user)
        return user

    def enter_piece(self, user_id: str, piece_id: str) -> ReadingView:
        """Enter a Piece as the head of the reader's active thread, and read it.

        The single entry / re-entry action of the guided journey. Permitted
        only for the current Daily Feature (the editorial front door — the
        first-run seed of the path) or a Piece already in the reader's own
        trail (a re-entry point). Any other Piece is a free-roam jump and is
        refused — V1 is a journey, not a search box.

        Entering deliberately starts a *fresh* active thread rooted at the
        Piece, resetting the backtrack stack; the durable history (visited
        nodes and pulled edges) is preserved. To continue a prior thread with
        its stack intact, use :meth:`resume` instead.

        Args:
            user_id: The reader entering the Piece.
            piece_id: The Piece to make the head of a fresh active thread.

        Returns:
            The destination Piece open for reading.

        Raises:
            UnknownUserError: If the reader has no identity.
            FreeRoamError: If the Piece is neither the Daily Feature nor visited.
        """
        self._require_user(user_id)
        journey = self._sessions.get_journey(user_id) or Journey.empty(user_id)
        if not (journey.has_visited(piece_id) or self._is_current_daily_feature(piece_id)):
            raise FreeRoamError(
                f"Piece {piece_id!r} is neither the Daily Feature nor already in the journey"
            )
        self._sessions.save_journey(journey.enter(piece_id))
        self._touch_session(user_id)
        return self._require_reading_view(piece_id)

    def pull_connection(self, user_id: str, from_piece_id: str, to_piece_id: str) -> ReadingView:
        """Pull a Connection to advance the path, and read the destination.

        Advances the single active thread one Connection at a time from where
        the reader actually stands — there is no jump across the graph.

        Args:
            user_id: The reader pulling the thread.
            from_piece_id: The origin, which must be the reader's current Piece.
            to_piece_id: The Connection's destination.

        Returns:
            The destination Piece open for reading.

        Raises:
            UnknownUserError: If the reader has no identity.
            NoJourneyError: If the reader has not entered a Piece yet.
            NotCurrentPieceError: If ``from_piece_id`` is not where they stand.
            UnknownConnectionError: If no such Connection exists.
        """
        self._require_user(user_id)
        journey = self._require_journey(user_id)
        if journey.current_piece_id != from_piece_id:
            raise NotCurrentPieceError(
                f"cannot pull from {from_piece_id!r}: the reader stands on "
                f"{journey.current_piece_id!r}"
            )
        if not self._connection_exists(from_piece_id, to_piece_id):
            raise UnknownConnectionError(f"no Connection from {from_piece_id!r} to {to_piece_id!r}")
        self._sessions.save_journey(journey.pull(to_piece_id))
        self._touch_session(user_id)
        return self._require_reading_view(to_piece_id)

    def backtrack(self, user_id: str) -> ReadingView:
        """Step back up the path the way the reader came, and read that Piece.

        Returns the reader to the prior Piece on the active thread (stack
        semantics), from where they may pull a different fork. Backtrack always
        leaves at least the thread's root standing, so a current Piece is
        guaranteed on return.

        Args:
            user_id: The reader stepping back.

        Returns:
            The prior Piece, open for reading.

        Raises:
            UnknownUserError: If the reader has no identity.
            NoJourneyError: If the reader has not entered a Piece yet.
            CannotBacktrackError: If they are already at the thread's root.
        """
        self._require_user(user_id)
        journey = self._require_journey(user_id).backtrack()
        self._sessions.save_journey(journey)
        self._touch_session(user_id)
        current = journey.current_piece_id
        assert current is not None
        return self._require_reading_view(current)

    def get_journey(self, user_id: str) -> JourneyView | None:
        """Return where the reader stands on their durable path.

        Args:
            user_id: The reader to resolve.

        Returns:
            The journey view (current Piece, backtrack stack, depth), or None
            if the reader has not started a path.
        """
        journey = self._sessions.get_journey(user_id)
        if journey is None:
            return None
        return JourneyView(
            current_piece_id=journey.current_piece_id,
            stack=journey.stack,
            depth=journey.depth,
        )

    def get_personal_knowledge_graph(self, user_id: str) -> PersonalKnowledgeGraph:
        """Return the reader's Personal Knowledge Graph — their own trail.

        The deduped union of the reader's Session paths: nodes are the distinct
        Pieces they read (seeded by their first Daily Feature and thickening
        every Session), edges are the Connections they pulled, and each node
        carries its Topics for colouring and clustering. Re-reading covered
        ground never adds a duplicate node — the trail is an honest map, not a
        tally.

        Args:
            user_id: The reader whose trail to render.

        Returns:
            The Personal Knowledge Graph; empty (no nodes or edges) if the
            reader has not started a path yet.

        Raises:
            UnknownUserError: If the reader has no identity.
        """
        self._require_user(user_id)
        journey = self._sessions.get_journey(user_id)
        if journey is None:
            return PersonalKnowledgeGraph(nodes=(), edges=())
        summaries = self._content.get_piece_summaries(journey.visited)
        nodes = tuple(
            PersonalKnowledgeGraphNode(
                piece_id=piece_id,
                title=summaries[piece_id].title,
                topics=summaries[piece_id].topics,
            )
            for piece_id in journey.visited
            if piece_id in summaries
        )
        edges = tuple(
            PersonalKnowledgeGraphEdge(
                from_piece_id=edge.from_piece_id, to_piece_id=edge.to_piece_id
            )
            for edge in journey.pulled
        )
        return PersonalKnowledgeGraph(nodes=nodes, edges=edges)

    def resume(self, user_id: str) -> ResumeView | None:
        """Continue the reader's thread: restore their current Piece and stack.

        The durable path outlives the analytics Session, so a coffee, a meeting,
        or a night's sleep never costs the reader their place. Resuming after
        the Session's window has closed opens a *new* window that continues the
        *same* path.

        Args:
            user_id: The reader resuming.

        Returns:
            The continue-your-thread view (current Piece, restored stack, and
            the Session it resumes in), or None if there is no path to resume.

        Raises:
            UnknownUserError: If the reader has no identity.
        """
        self._require_user(user_id)
        journey = self._sessions.get_journey(user_id)
        if journey is None or journey.current_piece_id is None:
            return None
        session = self._touch_session(user_id)
        return ResumeView(
            reading=self._require_reading_view(journey.current_piece_id),
            stack=journey.stack,
            session_id=session.id,
        )

    def close(self, user_id: str) -> None:
        """End the reader's current analytics Session (an explicit app close).

        The durable path is untouched — only the analytics window closes. The
        next activity or resume opens a fresh window continuing the same path.

        Args:
            user_id: The reader closing the app.

        Raises:
            UnknownUserError: If the reader has no identity.
        """
        self._require_user(user_id)
        session = self._sessions.get_current_session(user_id)
        if session is None or session.ended_at is not None:
            return
        self._sessions.save_session(replace(session, ended_at=self._clock.now()))

    def daily_notification(self, on: date | None = None) -> DailyNotification | None:
        """Compose the day's single dignified curiosity nudge (ADR 0009).

        Teases the Daily Feature's real hook and points at the very Piece it
        opens — never a nag, never a bait-and-switch, and never a gamification
        primitive.

        Args:
            on: The date to resolve the Daily Feature for; defaults to today.

        Returns:
            The notification, or None if no Daily Feature has been assigned.
        """
        feature = self._content.get_daily_feature(on)
        if feature is None:
            return None
        return DailyNotification(
            piece_id=feature.id,
            title=feature.title,
            teaser=feature.teaser,
        )

    def _touch_session(self, user_id: str) -> Session:
        """Record reader activity, opening a new analytics window if one is due.

        Continues the current window while it is open and within the inactivity
        budget; otherwise mints a fresh window (marking the stale one ended) —
        so a resume after the boundary is observably a new Session over the
        same durable path.

        Args:
            user_id: The active reader.

        Returns:
            The open Session the activity belongs to.
        """
        now = self._clock.now()
        current = self._sessions.get_current_session(user_id)
        if current is not None and not current.is_expired(now):
            active = replace(current, last_activity_at=now)
            self._sessions.save_session(active)
            return active
        if current is not None and current.ended_at is None:
            self._sessions.save_session(replace(current, ended_at=current.last_activity_at))
        fresh = Session(
            id=self._new_session_id(),
            user_id=user_id,
            started_at=now,
            last_activity_at=now,
        )
        self._sessions.save_session(fresh)
        return fresh

    def _reading_view(self, piece_id: str) -> ReadingView | None:
        """Build a reading view for a Piece, or None if it does not exist."""
        piece = self._content.get_piece(piece_id)
        if piece is None:
            return None
        return ReadingView(
            piece=piece,
            connections=self._content.get_connections_from(piece_id),
        )

    def _require_reading_view(self, piece_id: str) -> ReadingView:
        """Build a reading view for a Piece the caller has already proven exists.

        Callers reach here only after guarding the Piece's existence (it is the
        Daily Feature, a visited node, or a validated Connection destination),
        so the underlying lookup never comes back empty.
        """
        view = self._reading_view(piece_id)
        assert view is not None
        return view

    def _require_user(self, user_id: str) -> User:
        """Return the User or raise if the identity is unknown."""
        user = self._users.get(user_id)
        if user is None:
            raise UnknownUserError(f"unknown User id: {user_id!r}")
        return user

    def _require_journey(self, user_id: str) -> Journey:
        """Return the User's Journey or raise if it has not begun."""
        journey = self._sessions.get_journey(user_id)
        if journey is None or journey.current_piece_id is None:
            raise NoJourneyError(f"User {user_id!r} has not entered a Piece yet")
        return journey

    def _is_current_daily_feature(self, piece_id: str) -> bool:
        """Whether a Piece is today's Daily Feature (the allowed entry seed)."""
        feature = self._content.get_daily_feature()
        return feature is not None and feature.id == piece_id

    def _connection_exists(self, from_piece_id: str, to_piece_id: str) -> bool:
        """Whether an outbound Connection joins the two Pieces in the graph."""
        return any(
            preview.to_piece_id == to_piece_id
            for preview in self._content.get_connections_from(from_piece_id)
        )
