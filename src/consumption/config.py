"""Store selection by connection config — the reader's own tables.

The DSN is read from the environment (optionally via a local ``.env`` file),
never hardcoded, so pointing local dev at Docker and production at Supabase is
a config swap, not a code change. This is a *separate* store from the shared
Content Graph: consumption owns the user / session / path tables and only
*reads* the Content Graph through its port.
"""

import os
from collections.abc import Mapping
from dataclasses import dataclass

from dotenv import load_dotenv

from consumption.domain.errors import ConsumptionError

DSN_ENV_VAR = "CONSUMPTION_DSN"


class MissingConfigError(ConsumptionError):
    """A required configuration value is absent from the environment."""


@dataclass(frozen=True)
class ConsumptionConfig:
    """Connection configuration for the reader's store.

    Attributes:
        dsn: The Postgres connection string the adapters connect with.
    """

    dsn: str

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "ConsumptionConfig":
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
