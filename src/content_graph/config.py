"""Store selection by connection config — Docker <-> Supabase is a DSN swap.

The DSN is read from the shared ``DATABASE_URL`` (optionally via a local
``.env`` file), never hardcoded, so pointing local dev at Docker and production
at Supabase requires no code change. Consumption reads the same variable: both
subsystems live in one database, kept apart by module and schema ownership, not
by a physical split (ADR 0018).
"""

import os
from collections.abc import Mapping
from dataclasses import dataclass

from dotenv import load_dotenv

from content_graph.domain.errors import ContentGraphError

DSN_ENV_VAR = "DATABASE_URL"


class MissingConfigError(ContentGraphError):
    """A required configuration value is absent from the environment."""


@dataclass(frozen=True)
class ContentGraphConfig:
    """Connection configuration for the Content Graph store.

    Attributes:
        dsn: The Postgres connection string the adapter connects with.
    """

    dsn: str

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "ContentGraphConfig":
        """Build the config from the environment.

        Args:
            env: An explicit mapping to read from (for tests). When None,
                a local ``.env`` file is loaded and ``os.environ`` is used.

        Returns:
            The resolved configuration.

        Raises:
            MissingConfigError: If the DSN variable is not set.
        """
        if env is None:
            load_dotenv()
            env = os.environ
        dsn = env.get(DSN_ENV_VAR, "").strip()
        if not dsn:
            raise MissingConfigError(
                f"{DSN_ENV_VAR} is not set; see .env.example for the expected shape"
            )
        return cls(dsn=dsn)
