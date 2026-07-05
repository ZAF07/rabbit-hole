"""Issue 07 — the admin generation trigger: async, gated, status read-back."""

import threading
import time
from collections.abc import Callable
from itertools import count

import pytest
from fastapi.testclient import TestClient
from tests.api.conftest import TEST_SECRET, ClientFactory
from tests.consumption.clock import MutableClock

from api.app import create_app
from api.generation import GenerationService, Runner
from api.identity import AnonymousIdentity
from consumption.adapters.memory import InMemorySessionRepository, InMemoryUserRepository
from consumption.application.reader import ReaderService
from content_graph.adapters.memory import InMemoryContentGraphRepository

ADMIN_TOKEN = b"operator-secret"
ADMIN_HEADER = {"X-Admin-Token": "operator-secret"}
BRIEF = {"brief": "the invisible systems that move the physical world"}


class DeferredSpawn:
    """A spawn seam that captures thunks so a test runs them deterministically."""

    def __init__(self) -> None:
        self.thunks: list[Callable[[], None]] = []

    def __call__(self, thunk: Callable[[], None]) -> None:
        self.thunks.append(thunk)

    def run_all(self) -> None:
        """Run and clear every captured thunk (the background work, on demand)."""
        pending, self.thunks = self.thunks, []
        for thunk in pending:
            thunk()


def _fixed(run_id: str = "run-1") -> Callable[[], str]:
    """A run-id factory yielding a single fixed handle."""
    return lambda: run_id


def _ids() -> Callable[[], str]:
    counter = count(1)
    return lambda: f"run-{next(counter)}"


def _await_state(client: TestClient, run_id: str, expected: str, timeout: float = 3.0) -> str:
    """Poll a run's status until it reaches ``expected`` or the timeout lapses."""
    deadline = time.monotonic() + timeout
    state = ""
    while time.monotonic() < deadline:
        state = client.get(f"/admin/generation/runs/{run_id}", headers=ADMIN_HEADER).json()["state"]
        if state == expected:
            return state
        time.sleep(0.02)
    return state


def test_the_trigger_requires_the_operator_secret(build_client: ClientFactory) -> None:
    service = GenerationService(
        lambda run_id, brief: None, spawn=DeferredSpawn(), id_factory=_ids()
    )
    client = build_client(generation=service, admin_token=ADMIN_TOKEN)

    assert client.post("/admin/generation/runs", json=BRIEF).status_code == 401
    wrong = client.post("/admin/generation/runs", headers={"X-Admin-Token": "nope"}, json=BRIEF)
    assert wrong.status_code == 401
    accepted = client.post("/admin/generation/runs", headers=ADMIN_HEADER, json=BRIEF)
    assert accepted.status_code == 202


def test_a_reader_bearer_token_does_not_open_the_admin_route(build_client: ClientFactory) -> None:
    service = GenerationService(lambda run_id, brief: None, spawn=DeferredSpawn())
    client = build_client(generation=service, admin_token=ADMIN_TOKEN)

    refused = client.post(
        "/admin/generation/runs",
        headers={"Authorization": "Bearer a-reader-token"},  # the wrong credential
        json=BRIEF,
    )

    assert refused.status_code == 401


def test_the_trigger_returns_before_the_run_executes(build_client: ClientFactory) -> None:
    spawn = DeferredSpawn()
    ran: list[str] = []
    service = GenerationService(
        lambda run_id, brief: ran.append(run_id), spawn=spawn, id_factory=_fixed()
    )
    client = build_client(generation=service, admin_token=ADMIN_TOKEN)

    triggered = client.post("/admin/generation/runs", headers=ADMIN_HEADER, json=BRIEF)

    assert triggered.status_code == 202
    assert triggered.json()["run_id"] == "run-1"
    assert triggered.json()["state"] == "running"
    assert ran == []  # dispatched but not yet executed — the trigger did not block
    status = client.get("/admin/generation/runs/run-1", headers=ADMIN_HEADER)
    assert status.json()["state"] == "running"

    spawn.run_all()

    assert ran == ["run-1"]
    assert client.get("/admin/generation/runs/run-1", headers=ADMIN_HEADER).json()["state"] == (
        "succeeded"
    )


def test_the_trigger_is_non_blocking_and_readers_stay_responsive(
    build_client: ClientFactory,
) -> None:
    started = threading.Event()
    release = threading.Event()

    def runner(run_id: str, brief: str) -> None:
        started.set()
        assert release.wait(3)

    service = GenerationService(runner, id_factory=_fixed())  # real background thread
    client = build_client(generation=service, admin_token=ADMIN_TOKEN)

    triggered = client.post("/admin/generation/runs", headers=ADMIN_HEADER, json=BRIEF)
    assert triggered.status_code == 202
    assert triggered.json()["state"] == "running"
    assert started.wait(3)  # the run really began, off the request path

    assert client.get("/daily").status_code == 200  # readers unaffected while a run is in flight
    in_flight = client.get("/admin/generation/runs/run-1", headers=ADMIN_HEADER)
    assert in_flight.json()["state"] == "running"

    release.set()
    assert _await_state(client, "run-1", "succeeded") == "succeeded"


def test_a_failed_run_is_reported_with_its_reason(build_client: ClientFactory) -> None:
    def runner(run_id: str, brief: str) -> None:
        raise RuntimeError("the Architect refused the Brief")

    service = GenerationService(runner, id_factory=_fixed())
    client = build_client(generation=service, admin_token=ADMIN_TOKEN)

    client.post("/admin/generation/runs", headers=ADMIN_HEADER, json=BRIEF)

    assert _await_state(client, "run-1", "failed") == "failed"
    detail = client.get("/admin/generation/runs/run-1", headers=ADMIN_HEADER).json()["detail"]
    assert "refused the Brief" in detail


def test_an_unknown_run_is_not_found(build_client: ClientFactory) -> None:
    service = GenerationService(lambda run_id, brief: None, spawn=DeferredSpawn())
    client = build_client(generation=service, admin_token=ADMIN_TOKEN)

    assert client.get("/admin/generation/runs/ghost", headers=ADMIN_HEADER).status_code == 404


def test_the_admin_route_is_absent_when_generation_is_not_wired(client: TestClient) -> None:
    absent = client.post("/admin/generation/runs", headers=ADMIN_HEADER, json=BRIEF)

    assert absent.status_code == 404  # reader-only app never mounts the trigger


def test_mounting_generation_requires_an_admin_token() -> None:
    reader = ReaderService(
        content=InMemoryContentGraphRepository(),
        sessions=InMemorySessionRepository(),
        users=InMemoryUserRepository(),
        clock=MutableClock(),
    )
    service: GenerationService = GenerationService(_noop_runner())

    with pytest.raises(ValueError, match="admin_token"):
        create_app(reader=reader, identity=AnonymousIdentity(TEST_SECRET), generation=service)


def _noop_runner() -> Runner:
    return lambda run_id, brief: None
