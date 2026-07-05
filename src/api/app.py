"""The composition root — the one FastAPI app that is the backend deployable.

`create_app` takes its collaborators already built, so the same app runs over
the in-memory fakes in tests and over the Postgres adapters in production —
the store is a wiring choice, not a code change (ADR 0015). This app later
mounts the admin generation router; today it mounts the reader router alone.
"""

from fastapi import FastAPI

from api.admin import build_admin_router
from api.dependencies import get_identity, get_reader
from api.errors import register_error_handlers
from api.generation import GenerationService
from api.identity import AnonymousIdentity
from api.reader import build_reader_router
from consumption.application.reader import ReaderService


def create_app(
    *,
    reader: ReaderService,
    identity: AnonymousIdentity,
    generation: GenerationService | None = None,
    admin_token: bytes | None = None,
) -> FastAPI:
    """Wire the reader (and optionally the admin generation) routes into one app.

    Args:
        reader: The reader application service, already wired to its stores and
            the Content Graph read surface.
        identity: The anonymous-identity minter, already wired to its secret.
        generation: The generation service; when supplied, the admin trigger
            router is mounted onto the same app (ADR 0015). Omit to serve
            readers only.
        admin_token: The operator secret the admin gate checks; required when
            ``generation`` is supplied.

    Returns:
        The FastAPI app exposing the reader router — and the admin router when
        generation is wired — with reader-domain errors mapped to HTTP statuses.

    Raises:
        ValueError: If ``generation`` is supplied without an ``admin_token``.
    """
    app = FastAPI(title="Rabbit Hole — Backend API")
    app.state.reader = reader
    app.state.identity = identity
    register_error_handlers(app)
    app.include_router(build_reader_router())
    if generation is not None:
        if not admin_token:
            raise ValueError("an admin_token is required to mount the generation router")
        app.state.generation = generation
        app.state.admin_token = admin_token
        app.include_router(build_admin_router())
    return app


__all__ = ["AnonymousIdentity", "GenerationService", "create_app", "get_identity", "get_reader"]
