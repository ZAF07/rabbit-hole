"""The production DeepSeek adapter behind the ``LLMPort`` (ADR 0016).

DeepSeek is one provider behind the port; the provider is a config choice
(see :mod:`harness.adapters.llm_factory`). Every call goes out in JSON mode
and on the ``(model, temperature)`` tier its request purpose selects — V4
Flash near-0 for structural/judging purposes, V4 Pro higher for prose. A
bounded repair/transport retry recovers from a flaky connection or one
malformed generation; ``decode.py`` stays the single authority on response
*shape*, so a genuine, repeated contract mismatch surfaces as
:class:`~harness.errors.LLMResponseError`.

All LangChain/OpenAI imports are **lazy** — importing this module never
requires the ``llm`` extra, so offline installs and CI stay provider-free.
"""

import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from harness.config import LLMConfig, LLMTier
from harness.errors import HarnessError, LLMResponseError
from harness.ports.llm import LLMPort, LLMRequest, ToolSpec

PRECISE = "precise"
CREATIVE = "creative"

CREATIVE_PURPOSES = frozenset(
    {
        "writer.draft",
        "editor.revise",
        "editor.cut",
        "editor.qa",
        "weaver.hook",
    }
)

UNSUPPORTED_MODEL_MARKERS = ("reasoner",)

DEFAULT_REPAIR_RETRIES = 2


class UnsupportedModelError(HarnessError):
    """A configured model does not support JSON mode, function calling, and temperature."""


@dataclass(frozen=True)
class CallUsage:
    """Token usage recorded for one model call.

    Attributes:
        purpose: The request purpose.
        tier: The tier the call went out on (``precise``/``creative``).
        model: The model-id the call used.
        input_tokens: Prompt tokens the provider reported.
        output_tokens: Completion tokens the provider reported.
    """

    purpose: str
    tier: str
    model: str
    input_tokens: int
    output_tokens: int


def tier_for(purpose: str) -> str:
    """Classify a request purpose into its tier.

    Prose purposes (and the Editor's revision agent) are creative; everything
    else — structural and judging purposes, and the Researcher's navigation
    agent — is precise. An unlisted purpose defaults to precise (cheap and
    stable; a new prose purpose is a deliberate table edit, not a silent
    upgrade).

    Args:
        purpose: The request purpose.

    Returns:
        ``"precise"`` or ``"creative"``.
    """
    return CREATIVE if purpose in CREATIVE_PURPOSES else PRECISE


def _default_client_factory(
    config: LLMConfig, tier: LLMTier, http_client: Any | None, *, json_mode: bool
) -> Any:
    """Build a ``ChatDeepSeek`` for one tier (the only LangChain touch point).

    Args:
        config: The provider config (for the API key).
        tier: The ``(model, temperature)`` pair this client serves.
        http_client: An injected ``httpx.Client`` (tests inject a recorded
            transport); None uses the real network client.
        json_mode: Whether to force ``response_format=json_object``. On for
            single-shot ``complete`` calls; off for the ``run_agent`` tool
            loop, whose intermediate turns emit tool calls, not JSON (the
            final answer is still JSON per the authored instructions and is
            validated by ``decode.py``).

    Returns:
        A configured ``ChatDeepSeek``.
    """
    from langchain_deepseek import ChatDeepSeek

    kwargs: dict[str, Any] = {
        "model": tier.model,
        "api_key": config.api_key,
        "temperature": tier.temperature,
        "max_retries": 0,
    }
    if json_mode:
        kwargs["model_kwargs"] = {"response_format": {"type": "json_object"}}
    if http_client is not None:
        kwargs["http_client"] = http_client
    return ChatDeepSeek(**kwargs)


ClientFactory = Callable[..., Any]


class DeepSeekLLM(LLMPort):
    """DeepSeek behind the ``LLMPort`` — JSON mode, per-purpose tiers, bounded retry."""

    def __init__(
        self,
        config: LLMConfig,
        *,
        http_client: Any | None = None,
        client_factory: ClientFactory | None = None,
        repair_retries: int = DEFAULT_REPAIR_RETRIES,
    ) -> None:
        """Build the adapter, verifying both configured models are capable.

        Args:
            config: The resolved provider config.
            http_client: An injected ``httpx.Client`` for the client factory
                (tests inject a recorded transport).
            client_factory: Override for the ``ChatDeepSeek`` builder (tests).
            repair_retries: Extra attempts on transport error / malformed JSON.

        Raises:
            UnsupportedModelError: If either configured model looks incapable
                of JSON mode + function calling + temperature.
        """
        _verify_capabilities(config)
        self._config = config
        self._http_client = http_client
        self._client_factory = client_factory or _default_client_factory
        self._repair_retries = repair_retries
        self._clients: dict[str, Any] = {}
        self.usage: list[CallUsage] = []

    def complete(self, request: LLMRequest) -> str:
        """Run one JSON-mode call on the request's tier, with bounded retry.

        Args:
            request: The purpose-tagged request.

        Returns:
            The raw JSON response text (shape validated downstream by decode).

        Raises:
            LLMResponseError: If the response is persistently non-parseable
                past the retry budget (distinct from a transport failure).
        """
        tier_name = tier_for(request.purpose)
        messages = self._messages(request)
        last_error: Exception | None = None
        for _ in range(self._repair_retries + 1):
            try:
                content = self._invoke(request.purpose, tier_name, messages)
            except _transport_errors() as error:
                last_error = error
                continue
            if _is_json_object(content):
                return content
            last_error = LLMResponseError(f"{request.purpose}: response is not a JSON object")
        assert last_error is not None
        raise last_error

    def run_agent(self, request: LLMRequest, tools: Sequence[ToolSpec], *, step_limit: int) -> str:
        """Run a bounded ``create_agent`` loop over the tools.

        The authored spec is the agent's system prompt; the tools are the
        domain-neutral ``ToolSpec``s bound as LangChain tools; ``step_limit``
        caps the loop via ``recursion_limit``. The agent's final message is
        returned as JSON, decoded downstream by ``decode.py`` — the same
        authority on shape as every other call. LangChain lives entirely
        here; the domain never imports it.

        Args:
            request: The purpose-tagged request (``instructions`` is the
                system prompt, exactly as for ``complete``).
            tools: The tools the agent may call.
            step_limit: The agent-step budget (the ``recursion_limit``).

        Returns:
            The agent's final response text (JSON per the purpose's contract).
        """
        from langchain.agents import create_agent

        tier_name = tier_for(request.purpose)
        client = self._client(tier_name, json_mode=False)
        agent: Any = create_agent(
            client,
            tools=[_to_lc_tool(tool) for tool in tools],
            system_prompt=request.instructions,
        )
        human = _human_turn(
            request, "Use the available tools as needed, then respond with a single JSON object"
        )
        result = agent.invoke(
            {"messages": [("human", human)]}, config={"recursion_limit": step_limit}
        )
        messages = result["messages"]
        for message in messages:
            self._record_usage(request.purpose, tier_name, message)
        return _content_str(messages[-1].content)

    def _invoke(self, purpose: str, tier_name: str, messages: list[tuple[str, str]]) -> str:
        """Call the tier's client once and record usage.

        Args:
            purpose: The request purpose (for the usage record).
            tier_name: The tier to call on.
            messages: The (role, content) messages.

        Returns:
            The response content as a string.
        """
        client = self._client(tier_name, json_mode=True)
        result = client.invoke(messages)
        self._record_usage(purpose, tier_name, result)
        return _content_str(result.content)

    def _client(self, tier_name: str, *, json_mode: bool) -> Any:
        """Return the tier's client, building and caching it on first use.

        Args:
            tier_name: ``"precise"`` or ``"creative"``.
            json_mode: Whether the client forces JSON output (``complete``
                does; the ``run_agent`` tool loop does not).

        Returns:
            The tier's ``ChatDeepSeek`` client for this mode.
        """
        key = f"{tier_name}:{int(json_mode)}"
        if key not in self._clients:
            tier = self._config.creative if tier_name == CREATIVE else self._config.precise
            self._clients[key] = self._client_factory(
                self._config, tier, self._http_client, json_mode=json_mode
            )
        return self._clients[key]

    def _messages(self, request: LLMRequest) -> list[tuple[str, str]]:
        """Assemble the (system, human) messages for a request.

        The authored spec is the system prompt (the source of truth); the
        structured payload is the human turn, with an explicit JSON demand.

        Args:
            request: The purpose-tagged request.

        Returns:
            The messages for ``ChatDeepSeek.invoke``.
        """
        human = _human_turn(request, "Respond with a single JSON object")
        return [("system", request.instructions), ("human", human)]

    def _record_usage(self, purpose: str, tier_name: str, result: Any) -> None:
        """Record a call's token usage, if the provider reported it.

        Args:
            purpose: The request purpose.
            tier_name: The tier the call went out on.
            result: The message returned by ``invoke``.
        """
        meta = getattr(result, "usage_metadata", None) or {}
        tier = self._config.creative if tier_name == CREATIVE else self._config.precise
        self.usage.append(
            CallUsage(
                purpose=purpose,
                tier=tier_name,
                model=tier.model,
                input_tokens=int(meta.get("input_tokens", 0)),
                output_tokens=int(meta.get("output_tokens", 0)),
            )
        )


def _verify_capabilities(config: LLMConfig) -> None:
    """Fail loud if either configured model lacks the required capabilities.

    ``run_agent`` needs function calling, ``complete`` needs JSON mode, and
    every tier honors ``temperature``. The DeepSeek reasoner line historically
    supports none of the three together, so a model-id marked unsupported is
    rejected at build time rather than deep inside a run.

    Args:
        config: The provider config.

    Raises:
        UnsupportedModelError: If a configured model is marked unsupported.
    """
    for label, tier in (("precise", config.precise), ("creative", config.creative)):
        lowered = tier.model.lower()
        if any(marker in lowered for marker in UNSUPPORTED_MODEL_MARKERS):
            raise UnsupportedModelError(
                f"{label} tier model {tier.model!r} does not support JSON mode, "
                "function calling, and temperature together; use a DeepSeek V4 "
                "Flash or Pro model"
            )


def _human_turn(request: LLMRequest, closing: str) -> str:
    """Build the human message for a request — the structured payload + a JSON demand.

    The authored spec is the system prompt (the source of truth); this is the
    structured turn, with an explicit closing instruction that differs only
    between ``complete`` (respond) and ``run_agent`` (use tools, then respond).

    Args:
        request: The purpose-tagged request.
        closing: The final instruction line (per call shape).

    Returns:
        The human-turn text.
    """
    return (
        f"Purpose: {request.purpose}\n\n"
        f"Inputs (JSON):\n{json.dumps(request.payload, ensure_ascii=False)}\n\n"
        f"{closing} per the instructions above."
    )


def _to_lc_tool(spec: ToolSpec) -> Any:
    """Bind a domain-neutral ``ToolSpec`` to a LangChain structured tool.

    The tool framework is contained here; the stage that authored the
    ``ToolSpec`` imports no LangChain. The agent calls the tool with keyword
    args matching the spec's JSON schema; they are handed to ``spec.run`` as
    one mapping.

    Args:
        spec: The tool description.

    Returns:
        A LangChain ``StructuredTool`` wrapping the spec.
    """
    from langchain_core.tools import StructuredTool

    def _run(**kwargs: object) -> str:
        return spec.run(kwargs)

    return StructuredTool.from_function(
        func=_run,
        name=spec.name,
        description=spec.description,
        args_schema=dict(spec.parameters),
    )


def _is_json_object(text: str) -> bool:
    """Report whether text parses to a JSON object (the adapter's retry gate).

    Args:
        text: The response text.

    Returns:
        True if ``text`` is a JSON object; False otherwise.
    """
    try:
        return isinstance(json.loads(text), dict)
    except (json.JSONDecodeError, TypeError):
        return False


def _content_str(content: Any) -> str:
    """Coerce a message's content to a string.

    Args:
        content: The message content (a string, or a list of parts).

    Returns:
        The content as one string.
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            part if isinstance(part, str) else str(part.get("text", "")) for part in content
        )
    return str(content)


def _transport_errors() -> tuple[type[Exception], ...]:
    """The exception classes the retry treats as transport failures (lazy).

    Returns:
        A tuple of connection/timeout/API and httpx transport error classes.
    """
    import httpx
    import openai

    return (
        openai.APIConnectionError,
        openai.APITimeoutError,
        openai.APIError,
        httpx.TransportError,
    )
