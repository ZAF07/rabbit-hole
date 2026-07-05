"""Fixtures for the HTTP API suite.

The whole reader loop is driven over the wire with FastAPI's TestClient, wired
to the same in-memory fakes the application suite uses: an in-memory Content
Graph seeded with the fixture constellation, in-memory identity + path stores,
a hand-advanced clock, and an anonymous-identity minter with a fixed secret and
deterministic ids. No Postgres and no network — the loop is fully offline. The
``build_client`` factory lets the admin-router tests mount a generation service
onto the same app.
"""

from collections.abc import Callable
from itertools import count

import pytest
from fastapi.testclient import TestClient
from tests.consumption.clock import MutableClock
from tests.consumption.fixture_constellation import seed

from api.app import create_app
from api.generation import GenerationService
from api.identity import AnonymousIdentity
from consumption.adapters.memory import InMemorySessionRepository, InMemoryUserRepository
from consumption.application.reader import ReaderService
from content_graph.adapters.memory import InMemoryContentGraphRepository

TEST_SECRET = b"test-signing-secret"

ClientFactory = Callable[..., TestClient]


@pytest.fixture
def build_client() -> ClientFactory:
    """A factory that builds a TestClient over a freshly seeded reader app.

    Keyword args ``generation`` and ``admin_token`` are passed through to
    ``create_app`` so a test can mount the admin router when it needs one.
    """

    def _build(
        *,
        generation: GenerationService | None = None,
        admin_token: bytes | None = None,
    ) -> TestClient:
        content = InMemoryContentGraphRepository()
        seed(content)
        reader = ReaderService(
            content=content,
            sessions=InMemorySessionRepository(),
            users=InMemoryUserRepository(),
            clock=MutableClock(),
            id_factory=_counter("session"),
        )
        identity = AnonymousIdentity(TEST_SECRET, id_factory=_counter("user"))
        app = create_app(
            reader=reader,
            identity=identity,
            generation=generation,
            admin_token=admin_token,
        )
        return TestClient(app)

    return _build


@pytest.fixture
def client(build_client: ClientFactory) -> TestClient:
    """A reader-only TestClient (no admin router mounted)."""
    return build_client()


def _counter(prefix: str) -> Callable[[], str]:
    """A deterministic id factory: ``prefix-1``, ``prefix-2``, ..."""
    counter = count(1)
    return lambda: f"{prefix}-{next(counter)}"
