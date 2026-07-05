"""API configuration read from the environment — never hardcoded.

The identity signing secret is the one value the API layer needs beyond the
two stores' DSNs (each store owns its own DSN config). It is read from the
environment so it is set per deployment, not baked into the image.
"""

import os
from collections.abc import Mapping
from dataclasses import dataclass

from dotenv import load_dotenv

IDENTITY_SECRET_ENV_VAR = "API_IDENTITY_SECRET"
ADMIN_TOKEN_ENV_VAR = "API_ADMIN_TOKEN"


class MissingConfigError(Exception):
    """A required API configuration value is absent from the environment."""


@dataclass(frozen=True)
class ApiConfig:
    """Configuration for the HTTP API layer.

    Attributes:
        identity_secret: The HMAC key the anonymous-identity token is signed
            with; a leak lets a holder forge reader identities.
        admin_token: The operator secret the admin generation gate checks;
            None when the admin trigger is not enabled for this deployment.
    """

    identity_secret: bytes
    admin_token: bytes | None = None

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "ApiConfig":
        """Build the API config from the environment.

        Args:
            env: An explicit mapping to read from (for tests). When None, a
                local ``.env`` file is loaded and ``os.environ`` is used.

        Returns:
            The resolved configuration.

        Raises:
            MissingConfigError: If the identity secret is not set.
        """
        if env is None:
            load_dotenv()
            env = os.environ
        secret = env.get(IDENTITY_SECRET_ENV_VAR, "").strip()
        if not secret:
            raise MissingConfigError(
                f"{IDENTITY_SECRET_ENV_VAR} is not set; see .env.example for the expected shape"
            )
        admin = env.get(ADMIN_TOKEN_ENV_VAR, "").strip()
        return cls(
            identity_secret=secret.encode("utf-8"),
            admin_token=admin.encode("utf-8") if admin else None,
        )
