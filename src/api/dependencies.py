"""Dependency wiring for the reader router.

The composition root stashes the process-wide reader service and identity
minter on ``app.state``; these accessors hand them to route handlers, and
``current_user_id`` turns the request's bearer token into a reader identity —
minting a fresh one on first contact and echoing its token back so the client
can carry it thereafter.
"""

from typing import Annotated

from fastapi import Depends, Request, Response

from api.identity import AnonymousIdentity
from consumption.application.reader import ReaderService

TOKEN_HEADER = "X-Rabbit-Token"
_BEARER_PREFIX = "Bearer "


def get_reader(request: Request) -> ReaderService:
    """Return the process-wide reader service wired at app startup."""
    reader: ReaderService = request.app.state.reader
    return reader


def get_identity(request: Request) -> AnonymousIdentity:
    """Return the process-wide anonymous-identity minter wired at app startup."""
    identity: AnonymousIdentity = request.app.state.identity
    return identity


def _bearer_token(request: Request) -> str | None:
    """Extract the bearer token from the ``Authorization`` header, if present."""
    header = request.headers.get("authorization")
    if header is None or not header.startswith(_BEARER_PREFIX):
        return None
    token = header[len(_BEARER_PREFIX) :].strip()
    return token or None


def current_user_id(
    request: Request,
    response: Response,
    reader: Annotated[ReaderService, Depends(get_reader)],
    identity: Annotated[AnonymousIdentity, Depends(get_identity)],
) -> str:
    """Resolve the request's reader identity, minting one on first contact.

    A valid bearer token attributes the request to the reader it attests to. A
    missing or unverifiable token is treated as first contact: a fresh
    ``user_id`` is minted, registered, and its token echoed on the
    ``X-Rabbit-Token`` response header so the client stores and carries it on
    every later request.

    Args:
        request: The incoming request, carrying the bearer token if any.
        response: The outgoing response, to echo a freshly minted token on.
        reader: The reader service, used to register a newly minted identity.
        identity: The anonymous-identity minter / verifier.

    Returns:
        The ``user_id`` the request is attributed to.
    """
    token = _bearer_token(request)
    if token is not None:
        known = identity.verify(token)
        if known is not None:
            return known
    user_id, fresh_token = identity.mint()
    reader.create_user(user_id)
    response.headers[TOKEN_HEADER] = fresh_token
    return user_id


CurrentUser = Annotated[str, Depends(current_user_id)]
