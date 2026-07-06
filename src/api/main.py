"""Production wiring — the same app over Postgres, selected by config.

`create_app` is store-agnostic; this module supplies its real collaborators
from the environment: the shared Content Graph read adapter and the reader's
own user / session / path store, both Postgres, plus a system clock and the
identity secret. Pointing local dev at Docker and production at Supabase is a
DSN swap, never a code change (ADR 0015). Nothing here is imported by the
tests, which wire the in-memory fakes directly.
"""

import os
from collections.abc import Mapping
from pathlib import Path

import psycopg
from fastapi import FastAPI

from api.app import create_app
from api.config import ADMIN_TOKEN_ENV_VAR, ApiConfig
from api.generation import GenerationService
from api.identity import AnonymousIdentity
from consumption.adapters.clock import SystemClock
from consumption.adapters.migrate import apply_migrations
from consumption.adapters.postgres import PostgresSessionRepository, PostgresUserRepository
from consumption.application.reader import ReaderService
from consumption.config import ConsumptionConfig
from content_graph.adapters.postgres import PostgresContentGraphRepository
from content_graph.config import ContentGraphConfig
from content_graph.ports.repository import ContentGraphRepository
from harness.config import PROVIDER_ENV_VAR

HARNESS_ROOT_ENV_VAR = "HARNESS_ROOT"
FAN_OUT_ENV_VAR = "HARNESS_FAN_OUT"
DEFAULT_FAN_OUT = 4


def build_app_from_env() -> FastAPI:
    """Build the production app from environment configuration.

    Opens the Content Graph and consumption Postgres connections, applies the
    reader's own migrations, and wires the reader service and identity minter
    into the FastAPI app. When both ``LLM_PROVIDER`` and ``API_ADMIN_TOKEN``
    are configured, it also builds a real generation service (DeepSeek behind
    the ``LLMPort`` via the factory, plus the Playwright web port) and mounts
    the admin trigger — enabling generation is a deployment setting, not a
    redeploy (ADR 0016). With either absent the trigger stays dormant, and the
    reader path imports none of the generation machinery (ADR 0015).

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
    api_config = ApiConfig.from_env()
    identity = AnonymousIdentity(api_config.identity_secret)
    generation = _build_generation(content) if generation_configured() else None
    return create_app(
        reader=reader,
        identity=identity,
        generation=generation,
        admin_token=api_config.admin_token if generation is not None else None,
    )


def generation_configured(env: Mapping[str, str] | None = None) -> bool:
    """Whether the admin generation trigger should go live.

    Generation is enabled only when a provider is selected *and* the admin
    secret is set — both the model behind the port and the operator gate must
    be present, or the trigger stays dormant exactly as before.

    Args:
        env: An explicit mapping to read (for tests); ``os.environ`` by default.

    Returns:
        True when both the provider and the admin token are configured.
    """
    env = env if env is not None else os.environ
    return bool(env.get(PROVIDER_ENV_VAR, "").strip()) and bool(
        env.get(ADMIN_TOKEN_ENV_VAR, "").strip()
    )


def _build_generation(content: ContentGraphRepository) -> GenerationService:
    """Build the real generation service (lazy imports keep the extras optional).

    The provider SDK and Playwright are imported only here, so the dormant
    (reader-only) path never needs the ``llm``/``web`` extras. The run's model
    identity names the real DeepSeek models, so it is stamped on every Verdict.

    Args:
        content: The Content Graph the pipeline reads and writes.

    Returns:
        A generation service ready to mount behind the admin router.
    """
    from api.harness_runner import build_generation_service
    from harness.adapters.llm_factory import build_llm
    from harness.adapters.playwright_web import PlaywrightWebSource
    from harness.config import LLMConfig
    from harness.pipeline.context import HarnessConfig
    from harness.review.surface import WorkspaceVerdictGates
    from harness.specs import SpecLibrary

    llm_config = LLMConfig.from_env()
    root = Path(os.environ.get(HARNESS_ROOT_ENV_VAR, "") or _default_root())
    fan_out = int(os.environ.get(FAN_OUT_ENV_VAR, "") or DEFAULT_FAN_OUT)
    config = HarnessConfig(
        model=(f"{llm_config.provider}:{llm_config.precise.model}/{llm_config.creative.model}"),
        fan_out=fan_out,
    )
    return build_generation_service(
        repo=content,
        llm=build_llm(llm_config),
        web=PlaywrightWebSource(),
        gates=WorkspaceVerdictGates(),
        specs=SpecLibrary(repo_root=root),
        runs_root=root / "harness" / "runs",
        config=config,
    )


def _default_root() -> Path:
    """The repo root that holds the authored ``harness/`` specs and run workspaces.

    Returns:
        The repository root (overridable via ``HARNESS_ROOT``).
    """
    return Path(__file__).resolve().parents[2]


def main() -> None:
    """Serve the backend deployable with uvicorn."""
    import uvicorn

    uvicorn.run(build_app_from_env(), host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
