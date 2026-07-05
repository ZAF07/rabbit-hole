"""The admin router — trigger a generation run, read its state (ADR 0015).

Mounted on the same FastAPI app as the reader router, but gated separately: a
shared operator secret in the ``X-Admin-Token`` header, wholly distinct from
the reader's anonymous identity. The trigger dispatches the run in-process and
returns ``202`` at once; a status endpoint lets the operator follow it. The
router touches the harness only through the injected ``GenerationService`` — it
imports no generation code itself (the wiring lives in the composition root).
"""

import hmac
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel

from api.generation import GenerationService, RunRecord

ADMIN_TOKEN_HEADER = "X-Admin-Token"


class TriggerRequest(BaseModel):
    """A request to trigger a generation run."""

    brief: str


class RunHandleDTO(BaseModel):
    """A triggered run's handle and current state."""

    run_id: str
    state: str
    detail: str = ""


def _run_handle(record: RunRecord) -> RunHandleDTO:
    """Convert a run record to its wire handle — the single translation point."""
    return RunHandleDTO(run_id=record.run_id, state=record.state.value, detail=record.detail)


def _generation(request: Request) -> GenerationService:
    """Return the process-wide generation service wired at app startup."""
    service: GenerationService = request.app.state.generation
    return service


def _admin_secret(request: Request) -> bytes:
    """Return the operator secret the admin gate checks against."""
    secret: bytes = request.app.state.admin_token
    return secret


def require_admin(
    admin_secret: Annotated[bytes, Depends(_admin_secret)],
    x_admin_token: Annotated[str | None, Header()] = None,
) -> None:
    """Reject any request without the operator's shared secret.

    The admin gate is deliberately separate from reader identity: no minted
    token, no anonymous user, opens it — only the configured operator secret.

    Args:
        admin_secret: The configured operator secret.
        x_admin_token: The secret presented on the ``X-Admin-Token`` header.

    Raises:
        HTTPException: 401 if the header is absent or does not match.
    """
    presented = (x_admin_token or "").encode("utf-8")
    if not hmac.compare_digest(presented, admin_secret):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "operator authentication required")


Generation = Annotated[GenerationService, Depends(_generation)]


def build_admin_router() -> APIRouter:
    """Build the admin generation router, gated by the operator secret.

    Returns:
        The router exposing the async trigger and the run-status read-back,
        every route guarded by :func:`require_admin`.
    """
    router = APIRouter(
        prefix="/admin/generation",
        tags=["admin"],
        dependencies=[Depends(require_admin)],
    )

    @router.post("/runs", status_code=status.HTTP_202_ACCEPTED)
    def trigger(body: TriggerRequest, generation: Generation) -> RunHandleDTO:
        """Start a generation run and return its handle immediately."""
        return _run_handle(generation.launch(body.brief))

    @router.get("/runs/{run_id}")
    def get_run(run_id: str, generation: Generation) -> RunHandleDTO:
        """Report a triggered run's current state."""
        record = generation.get(run_id)
        if record is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"unknown run: {run_id!r}")
        return _run_handle(record)

    return router
