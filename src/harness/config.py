"""Provider selection by config — turning on real generation is a setting.

The LLM provider, its API key, and the two per-purpose tiers (a
``(model, temperature)`` pair each) are read from the environment
(optionally via a local ``.env`` file), never hardcoded, so selecting the
provider, re-tiering, or bumping a model is deployment configuration rather
than a code change (ADR 0016 Decisions 1, 5). This mirrors the store's
``ContentGraphConfig.from_env`` pattern.
"""

import os
from collections.abc import Mapping
from dataclasses import dataclass

from dotenv import load_dotenv

from harness.errors import HarnessError

PROVIDER_ENV_VAR = "LLM_PROVIDER"
API_KEY_ENV_VAR = "LLM_API_KEY"
PRECISE_MODEL_ENV_VAR = "LLM_MODEL_PRECISE"
CREATIVE_MODEL_ENV_VAR = "LLM_MODEL_CREATIVE"
PRECISE_TEMPERATURE_ENV_VAR = "LLM_TEMPERATURE_PRECISE"
CREATIVE_TEMPERATURE_ENV_VAR = "LLM_TEMPERATURE_CREATIVE"

DEFAULT_PRECISE_TEMPERATURE = 0.0
DEFAULT_CREATIVE_TEMPERATURE = 1.0


class MissingConfigError(HarnessError):
    """A required LLM configuration value is absent from the environment."""


class MalformedConfigError(HarnessError, ValueError):
    """An LLM configuration value is present but could not be parsed."""


@dataclass(frozen=True)
class LLMTier:
    """One purpose tier — the ``(model, temperature)`` pair a call goes out on.

    Attributes:
        model: The provider model-id (e.g. a DeepSeek V4 Flash or Pro id).
        temperature: The sampling temperature for this tier.
    """

    model: str
    temperature: float


@dataclass(frozen=True)
class LLMConfig:
    """Provider selection and the two per-purpose tiers.

    Attributes:
        provider: The selected provider (the ``build_llm`` registry key).
        api_key: The provider API key.
        precise: The precise tier — structural/judging purposes and the
            Researcher's navigation agent (near-0 temperature).
        creative: The creative tier — prose purposes and the Editor's
            revision agent (higher temperature).
    """

    provider: str
    api_key: str
    precise: LLMTier
    creative: LLMTier

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "LLMConfig":
        """Build the config from the environment.

        Args:
            env: An explicit mapping to read from (for tests). When None, a
                local ``.env`` file is loaded and ``os.environ`` is used.

        Returns:
            The resolved configuration.

        Raises:
            MissingConfigError: If a required variable (provider, API key, or
                either model-id) is absent or empty; the message names it.
            MalformedConfigError: If a temperature is present but not a float.
        """
        if env is None:
            load_dotenv()
            env = os.environ
        return cls(
            provider=_require(env, PROVIDER_ENV_VAR),
            api_key=_require(env, API_KEY_ENV_VAR),
            precise=LLMTier(
                model=_require(env, PRECISE_MODEL_ENV_VAR),
                temperature=_temperature(
                    env, PRECISE_TEMPERATURE_ENV_VAR, DEFAULT_PRECISE_TEMPERATURE
                ),
            ),
            creative=LLMTier(
                model=_require(env, CREATIVE_MODEL_ENV_VAR),
                temperature=_temperature(
                    env, CREATIVE_TEMPERATURE_ENV_VAR, DEFAULT_CREATIVE_TEMPERATURE
                ),
            ),
        )


def _require(env: Mapping[str, str], name: str) -> str:
    """Read a required value, failing loud and naming the variable if absent.

    Args:
        env: The environment mapping.
        name: The variable name.

    Returns:
        The stripped value.

    Raises:
        MissingConfigError: If the value is absent or empty.
    """
    value = env.get(name, "").strip()
    if not value:
        raise MissingConfigError(f"{name} is not set; see .env.example for the expected shape")
    return value


def _temperature(env: Mapping[str, str], name: str, default: float) -> float:
    """Read an optional temperature, defaulting when absent, failing loud if malformed.

    Args:
        env: The environment mapping.
        name: The variable name.
        default: The tier default when the variable is absent.

    Returns:
        The parsed temperature.

    Raises:
        MalformedConfigError: If the value is present but not a float.
    """
    raw = env.get(name, "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError as error:
        raise MalformedConfigError(f"{name} must be a number, got {raw!r}") from error
