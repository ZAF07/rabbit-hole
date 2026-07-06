"""Provider selection — ``LLM_PROVIDER`` maps to an ``LLMPort`` adapter.

Adding a second provider is a new adapter class + one registry line + a new
``LLM_PROVIDER`` value; the pipeline never changes (ADR 0016 Decision 1).
"""

from collections.abc import Callable

from harness.config import LLMConfig
from harness.errors import HarnessError
from harness.ports.llm import LLMPort

Builder = Callable[[LLMConfig], LLMPort]


class UnknownProviderError(HarnessError):
    """The configured ``LLM_PROVIDER`` has no registered adapter builder."""


def _build_deepseek(config: LLMConfig) -> LLMPort:
    """Build the DeepSeek adapter (lazy import keeps the core provider-free).

    Args:
        config: The resolved provider config.

    Returns:
        The DeepSeek ``LLMPort`` adapter.
    """
    from harness.adapters.deepseek import DeepSeekLLM

    return DeepSeekLLM(config)


_REGISTRY: dict[str, Builder] = {
    "deepseek": _build_deepseek,
}


def build_llm(config: LLMConfig) -> LLMPort:
    """Return the ``LLMPort`` adapter selected by ``config.provider``.

    Args:
        config: The resolved provider config.

    Returns:
        The selected adapter.

    Raises:
        UnknownProviderError: If no builder is registered for the provider.
    """
    builder = _REGISTRY.get(config.provider)
    if builder is None:
        known = ", ".join(sorted(_REGISTRY)) or "(none)"
        raise UnknownProviderError(
            f"no LLM adapter registered for provider {config.provider!r}; known: {known}"
        )
    return builder(config)
