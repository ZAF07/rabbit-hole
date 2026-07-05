"""The reader router — the core loop on the wire.

HTTP endpoints over the reader use-cases: land on the Daily Feature, read a
Piece into the active thread, pull a Connection onward, backtrack, resume after
a break, and view the growing trail. Reading a Piece is the *guarded* entry
action (`enter_piece`): only the Daily Feature or a Piece already in the
reader's trail may be opened — there is no free-roam read of an arbitrary Piece
(user story 12). Every response is a DTO carrying internal vocabulary only.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status

from api.dependencies import CurrentUser, get_reader
from api.dtos import (
    DailyFeatureDTO,
    JourneyDTO,
    KnowledgeGraphDTO,
    NotificationDTO,
    PullRequest,
    ReadingDTO,
    ResumeDTO,
    daily_feature_dto,
    journey_dto,
    knowledge_graph_dto,
    notification_dto,
    reading_dto,
    resume_dto,
)
from consumption.application.reader import ReaderService

Reader = Annotated[ReaderService, Depends(get_reader)]


def build_reader_router() -> APIRouter:
    """Build the reader router — the six use-cases plus the loop's book-ends.

    Returns:
        The router exposing the Daily Feature, read, pull, backtrack, journey,
        resume, close, and Personal Knowledge Graph endpoints.
    """
    router = APIRouter(tags=["reader"])

    @router.get("/daily")
    def get_daily_feature(reader: Reader, _user: CurrentUser) -> DailyFeatureDTO:
        """Land on the day's featured Piece with a peek at where it Connects."""
        feature = reader.get_daily_feature()
        if feature is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "no Daily Feature has been assigned")
        return daily_feature_dto(feature)

    @router.get("/notification")
    def get_daily_notification(reader: Reader, _user: CurrentUser) -> NotificationDTO:
        """Fetch the day's single dignified curiosity nudge."""
        notification = reader.daily_notification()
        if notification is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "no Daily Feature has been assigned")
        return notification_dto(notification)

    @router.post("/pieces/{piece_id}/read")
    def read_piece(piece_id: str, reader: Reader, user: CurrentUser) -> ReadingDTO:
        """Open a Piece into the active thread and read it (guarded entry)."""
        return reading_dto(reader.enter_piece(user, piece_id))

    @router.post("/pull")
    def pull_connection(request: PullRequest, reader: Reader, user: CurrentUser) -> ReadingDTO:
        """Pull a Connection to advance the thread and read the destination."""
        return reading_dto(reader.pull_connection(user, request.from_piece_id, request.to_piece_id))

    @router.post("/backtrack")
    def backtrack(reader: Reader, user: CurrentUser) -> ReadingDTO:
        """Step back up the thread the way the reader came, and read that Piece."""
        return reading_dto(reader.backtrack(user))

    @router.get("/journey")
    def get_journey(reader: Reader, user: CurrentUser) -> JourneyDTO:
        """Report where the reader stands on their durable path."""
        journey = reader.get_journey(user)
        if journey is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "the reader has not started a journey")
        return journey_dto(journey)

    @router.get("/resume")
    def resume(reader: Reader, user: CurrentUser, response: Response) -> ResumeDTO | None:
        """Continue the reader's thread: restore their current Piece and stack."""
        resumed = reader.resume(user)
        if resumed is None:
            response.status_code = status.HTTP_204_NO_CONTENT
            return None
        return resume_dto(resumed)

    @router.post("/close", status_code=status.HTTP_204_NO_CONTENT)
    def close(reader: Reader, user: CurrentUser) -> None:
        """End the reader's current analytics Session (an explicit app close)."""
        reader.close(user)

    @router.get("/knowledge-graph")
    def get_knowledge_graph(reader: Reader, user: CurrentUser) -> KnowledgeGraphDTO:
        """Return the reader's own trail — distinct Pieces read, Connections pulled."""
        return knowledge_graph_dto(reader.get_personal_knowledge_graph(user))

    return router
