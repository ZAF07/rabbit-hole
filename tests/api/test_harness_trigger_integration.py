"""Issue 07 — the admin trigger drives the *real* harness pipeline.

The fake-runner tests pin the router's async / auth / status contract; this one
proves the composition itself: a trigger over HTTP builds a RunContext and runs
the actual ``run_pipeline`` over its ports, writing a constellation into the
Content Graph. A synchronous spawn runs the pipeline inline so the assertion is
deterministic — the async behaviour is covered separately.
"""

from collections.abc import Callable
from pathlib import Path

from tests.api.conftest import ClientFactory
from tests.harness.fixture_run import (
    FIXTURE_GOAL,
    PIECE_IDS,
    REPO_ROOT,
    fixture_web_source,
    well_behaved_llm,
)

from api.harness_runner import build_generation_service
from content_graph.adapters.memory import InMemoryContentGraphRepository
from harness.review.gates import AutoApproveGates
from harness.specs import SpecLibrary

ADMIN_HEADER = {"X-Admin-Token": "operator-secret"}
ADMIN_TOKEN = b"operator-secret"


def _synchronous_spawn(thunk: Callable[[], None]) -> None:
    """Run the dispatched work inline, so the pipeline completes before the assert."""
    thunk()


def test_the_trigger_runs_the_pipeline_and_writes_the_constellation(
    build_client: ClientFactory, tmp_path: Path
) -> None:
    repo = InMemoryContentGraphRepository()
    service = build_generation_service(
        repo=repo,
        llm=well_behaved_llm(),
        web=fixture_web_source(),
        gates=AutoApproveGates(),
        specs=SpecLibrary(repo_root=REPO_ROOT),
        runs_root=tmp_path,
        spawn=_synchronous_spawn,
        id_factory=lambda: "run-1",
    )
    client = build_client(generation=service, admin_token=ADMIN_TOKEN)

    triggered = client.post(
        "/admin/generation/runs", headers=ADMIN_HEADER, json={"brief": FIXTURE_GOAL}
    )
    assert triggered.status_code == 202

    status = client.get("/admin/generation/runs/run-1", headers=ADMIN_HEADER).json()
    assert status["state"] == "succeeded", status

    published = {summary.id for summary in repo.list_piece_summaries()}
    assert set(PIECE_IDS) <= published  # the real pipeline wrote the Pieces through the port
