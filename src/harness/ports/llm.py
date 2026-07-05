"""The LLM port — every model call in the pipeline goes through here.

Requests are purpose-tagged and structured so adapters can assemble the
real prompt from the markdown specs, and fakes can dispatch on purpose.
Responses are JSON text parsed by the calling stage against its contract.
"""

from abc import ABC, abstractmethod
from collections.abc import Mapping
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
