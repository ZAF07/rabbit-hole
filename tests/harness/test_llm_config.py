"""Issue 01 — LLMConfig.from_env reads provider/key/tiers, fails loud on absence."""

import pytest

from harness.config import (
    API_KEY_ENV_VAR,
    CREATIVE_MODEL_ENV_VAR,
    CREATIVE_TEMPERATURE_ENV_VAR,
    DEFAULT_CREATIVE_TEMPERATURE,
    DEFAULT_PRECISE_TEMPERATURE,
    PRECISE_MODEL_ENV_VAR,
    PRECISE_TEMPERATURE_ENV_VAR,
    PROVIDER_ENV_VAR,
    LLMConfig,
    MalformedConfigError,
    MissingConfigError,
)

FULL_ENV = {
    PROVIDER_ENV_VAR: "deepseek",
    API_KEY_ENV_VAR: "sk-test-key",
    PRECISE_MODEL_ENV_VAR: "deepseek-v4-flash",
    CREATIVE_MODEL_ENV_VAR: "deepseek-v4-pro",
    PRECISE_TEMPERATURE_ENV_VAR: "0.1",
    CREATIVE_TEMPERATURE_ENV_VAR: "1.3",
}


def test_from_env_reads_provider_key_models_and_temperatures():
    config = LLMConfig.from_env(dict(FULL_ENV))
    assert config.provider == "deepseek"
    assert config.api_key == "sk-test-key"
    assert config.precise.model == "deepseek-v4-flash"
    assert config.precise.temperature == 0.1
    assert config.creative.model == "deepseek-v4-pro"
    assert config.creative.temperature == 1.3


def test_temperatures_default_when_absent():
    env = {k: v for k, v in FULL_ENV.items() if "TEMPERATURE" not in k}
    config = LLMConfig.from_env(env)
    assert config.precise.temperature == DEFAULT_PRECISE_TEMPERATURE
    assert config.creative.temperature == DEFAULT_CREATIVE_TEMPERATURE


@pytest.mark.parametrize(
    "missing",
    [PROVIDER_ENV_VAR, API_KEY_ENV_VAR, PRECISE_MODEL_ENV_VAR, CREATIVE_MODEL_ENV_VAR],
)
def test_missing_required_value_fails_loud_naming_the_variable(missing):
    env = {k: v for k, v in FULL_ENV.items() if k != missing}
    with pytest.raises(MissingConfigError) as excinfo:
        LLMConfig.from_env(env)
    assert missing in str(excinfo.value)


def test_empty_required_value_fails_loud():
    env = {**FULL_ENV, API_KEY_ENV_VAR: "   "}
    with pytest.raises(MissingConfigError) as excinfo:
        LLMConfig.from_env(env)
    assert API_KEY_ENV_VAR in str(excinfo.value)


def test_malformed_temperature_fails_loud():
    env = {**FULL_ENV, PRECISE_TEMPERATURE_ENV_VAR: "hot"}
    with pytest.raises(MalformedConfigError) as excinfo:
        LLMConfig.from_env(env)
    assert PRECISE_TEMPERATURE_ENV_VAR in str(excinfo.value)
