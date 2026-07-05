"""Production wiring — the same app over Postgres, selected by config.

`create_app` is store-agnostic; this module supplies its real collaborators
from the environment: the shared Content Graph read adapter and the reader's
own user / session / path store, both Postgres, plus a system clock and the
identity secret. Pointing local dev at Docker and production at Supabase is a
DSN swap, never a code change (ADR 0015). Nothing here is imported by the
tests, which wire the in-memory fakes directly.
"""

import psycopg
from fastapi import FastAPI

from api.app import create_app
from api.config import ApiConfig
from api.identity import AnonymousIdentity
from consumption.adapters.clock import SystemClock
from consumption.adapters.migrate import apply_migrations
from consumption.adapters.postgres import PostgresSessionRepository, PostgresUserRepository
from consumption.application.reader import ReaderService
from consumption.config import ConsumptionConfig
from content_graph.adapters.postgres import PostgresContentGraphRepository
from content_graph.config import ContentGraphConfig


def build_app_from_env() -> FastAPI:
    """Build the production app from environment configuration.

    Opens the Content Graph and consumption Postgres connections, applies the
    reader's own migrations, and wires the reader service and identity minter
    into the FastAPI app.

    The admin generation trigger stays dormant here on purpose: no production
    LLM adapter exists yet (runs are driven through a scripted ``LLMPort`` in
    tests/dev — see CLAUDE.md). To enable it, build a generation service with
    :func:`api.harness_runner.build_generation_service` over real LLM/web ports
    and pass it (with the ``API_ADMIN_TOKEN`` secret) to :func:`create_app`.

    Returns:
        The fully wired FastAPI application.
    """
    content = PostgresContentGraphRepository.from_config(ContentGraphConfig.from_env())

    consumption_config = ConsumptionConfig.from_env()
    reader_conn = psycopg.connect(consumption_config.dsn)
    apply_migrations(reader_conn)

    reader = ReaderService(
        content=content,
        sessions=PostgresSessionRepository(reader_conn),
        users=PostgresUserRepository(reader_conn),
        clock=SystemClock(),
    )
    identity = AnonymousIdentity(ApiConfig.from_env().identity_secret)
    return create_app(reader=reader, identity=identity)


def main() -> None:
    """Serve the backend deployable with uvicorn."""
    import uvicorn

    uvicorn.run(build_app_from_env(), host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
