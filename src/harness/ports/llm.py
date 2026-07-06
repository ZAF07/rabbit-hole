"""The LLM port — every model call in the pipeline goes through here.

Requests are purpose-tagged and structured so adapters can assemble the
real prompt from the markdown specs, and fakes can dispatch on purpose.
Responses are JSON text parsed by the calling stage against its contract.

The port has two shapes. ``complete`` is a single-shot call. ``run_agent``
lets a stage delegate a *bounded local decision* to an agent loop over
domain-neutral :class:`ToolSpec`s — the agent framework (LangChain's
``create_agent``, tool-binding, ``recursion_limit``) lives entirely behind
the adapter, so the domain never imports it (ADR 0016 Decision 2).
"""

from abc import ABC, abstractmethod
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field


@dataclass(frozen=True)
class LLMRequest:
    """One purpose-tagged model call.

    Attributes:
        purpose: The stage-scoped intent, e.g. ``"architect.plan"`` or
            ``"editor.judge"`` — the dispatch key for adapters and fakes.
        instructions: The spec text assembled for the call (DNA, Voice
            Profile, guardrails, agent card) — the markdown source of truth.
        payload: The structured inputs (Brief fields, claim pack, blocks…).
    """

    purpose: str
    instructions: str = ""
    payload: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Freeze a defensive copy of the payload."""
        object.__setattr__(self, "payload", dict(self.payload))


@dataclass(frozen=True)
class ToolSpec:
    """A framework-neutral description of a tool an agent may call.

    A stage describes *what a tool does* — its name, a natural-language
    description, and a JSON-schema for its arguments — plus a callable that
    runs it. The adapter binds these to the agent framework; the stage
    imports no agent framework to create one.

    Attributes:
        name: The tool's identifier the agent calls it by.
        description: What the tool does, for the agent's tool-choice.
        parameters: The JSON schema for the tool's arguments.
        run: The callable the adapter invokes with decoded args; its
            string return is what the agent reads back.
    """

    name: str
    description: str
    parameters: Mapping[str, object]
    run: Callable[[Mapping[str, object]], str]


class LLMPort(ABC):
    """Text-completion seam; the response is JSON per the purpose's contract."""

    @abstractmethod
    def complete(self, request: LLMRequest) -> str:
        """Run one model call.

        Args:
            request: The purpose-tagged request.

        Returns:
            The raw response text (JSON for every pipeline purpose).
        """

    @abstractmethod
    def run_agent(self, request: LLMRequest, tools: Sequence[ToolSpec], *, step_limit: int) -> str:
        """Run a bounded agent loop over the given tools.

        The agent may call the supplied tools up to ``step_limit`` steps to
        navigate or revise toward the request's goal, then returns its final
        answer as JSON — decoded by the same ``decode.py`` as every other
        call, so response shape has one authority.

        Args:
            request: The purpose-tagged request; ``instructions`` is the
                agent's system prompt (the authored spec), exactly as for
                ``complete``.
            tools: The domain-neutral tools the agent may call.
            step_limit: The maximum number of agent steps (bounds spend and
                runaway loops).

        Returns:
            The agent's final response text (JSON for every pipeline purpose).
        """
