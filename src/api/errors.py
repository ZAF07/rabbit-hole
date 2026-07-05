"""Maps reader-domain errors to HTTP status codes at the edge.

The reader use-cases raise domain errors that name *what* went wrong; the API
is the one place that decides the *transport* meaning. Keeping the mapping here
leaves the application service free of HTTP concerns.
"""

from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from consumption.domain.errors import (
    CannotBacktrackError,
    ConsumptionError,
    FreeRoamError,
    NoJourneyError,
    NotCurrentPieceError,
    UnknownConnectionError,
    UnknownUserError,
)

_STATUS_BY_ERROR: dict[type[ConsumptionError], int] = {
    UnknownUserError: 401,
    FreeRoamError: 403,
    UnknownConnectionError: 404,
    NoJourneyError: 409,
    NotCurrentPieceError: 409,
    CannotBacktrackError: 409,
}


def _handler(status_code: int) -> Callable[[Request, Exception], Awaitable[JSONResponse]]:
    """Build a handler that renders an error as a JSON body at ``status_code``."""

    async def handle(_request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(status_code=status_code, content={"detail": str(exc)})

    return handle


def register_error_handlers(app: FastAPI) -> None:
    """Register the reader-error → HTTP-status mapping on the app.

    Args:
        app: The FastAPI application to register handlers on.
    """
    for error_type, status_code in _STATUS_BY_ERROR.items():
        app.add_exception_handler(error_type, _handler(status_code))
