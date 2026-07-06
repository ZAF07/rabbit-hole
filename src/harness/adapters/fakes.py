"""Deterministic fakes for both ports — the offline test substrate.

With these two fakes plus the in-memory ``ContentGraphRepository`` from
content_graph, the whole pipeline runs end-to-end offline (ADR 0011's
stated payoff). The scripted LLM dispatches on request purpose; tests
register or replace handlers per purpose to steer behavior.
"""

from collections.abc import Callable, Mapping, Sequence

from harness.ports.llm import LLMPort, LLMRequest, ToolSpec
from harness.ports.web_source import FetchedPage, WebSourcePort

Handler = Callable[[LLMRequest], str]
AgentHandler = Callable[[LLMRequest, Sequence[ToolSpec], int], str]


class ScriptedLLM(LLMPort):
    """Purpose-dispatched fake LLM with recordable requests."""

    def __init__(
        self,
        handlers: Mapping[str, Handler] | None = None,
        agent_handlers: Mapping[str, AgentHandler] | None = None,
    ) -> None:
        """Create the fake.

        Args:
            handlers: Initial purpose → ``complete`` handler mapping.
            agent_handlers: Initial purpose → ``run_agent`` handler mapping;
                each handler receives the request, the bound tools, and the
                step limit so it can drive the tools deterministically.
        """
        self._handlers: dict[str, Handler] = dict(handlers or {})
        self._agent_handlers: dict[str, AgentHandler] = dict(agent_handlers or {})
        self.requests: list[LLMRequest] = []

    def on(self, purpose: str, handler: Handler) -> None:
        """Register or replace the ``complete`` handler for one purpose.

        Args:
            purpose: The request purpose to intercept.
            handler: The function producing the response text.
        """
        self._handlers[purpose] = handler

    def on_agent(self, purpose: str, handler: AgentHandler) -> None:
        """Register or replace the ``run_agent`` handler for one purpose.

        Args:
            purpose: The request purpose to intercept.
            handler: The function driving the tools and producing the JSON.
        """
        self._agent_handlers[purpose] = handler

    def complete(self, request: LLMRequest) -> str:
        """Dispatch a request to its purpose handler.

        Args:
            request: The purpose-tagged request.

        Returns:
            The handler's response text.

        Raises:
            KeyError: If no handler is registered for the purpose.
        """
        self.requests.append(request)
        handler = self._handlers.get(request.purpose)
        if handler is None:
            raise KeyError(f"ScriptedLLM has no handler for purpose {request.purpose!r}")
        return handler(request)

    def run_agent(self, request: LLMRequest, tools: Sequence[ToolSpec], *, step_limit: int) -> str:
        """Drive the purpose's agent handler over the supplied tools.

        The handler invokes the ``ToolSpec`` callables itself, so the wrapped
        tools are genuinely exercised offline; the request is recorded on
        ``requests`` exactly as ``complete`` records its own.

        Args:
            request: The purpose-tagged request.
            tools: The tools bound for this call.
            step_limit: The step budget passed through to the handler.

        Returns:
            The handler's response text (JSON per the purpose's contract).

        Raises:
            KeyError: If no agent handler is registered for the purpose.
        """
        self.requests.append(request)
        handler = self._agent_handlers.get(request.purpose)
        if handler is None:
            raise KeyError(f"ScriptedLLM has no agent handler for purpose {request.purpose!r}")
        return handler(request, tuple(tools), step_limit)


class FakeWebSource(WebSourcePort):
    """Canned pages keyed by URL; records every fetch."""

    def __init__(self, pages: Mapping[str, FetchedPage] | None = None) -> None:
        """Create the fake.

        Args:
            pages: URL → canned page.
        """
        self._pages: dict[str, FetchedPage] = dict(pages or {})
        self.fetched: list[str] = []

    def add(self, page: FetchedPage) -> None:
        """Add one canned page.

        Args:
            page: The page, keyed by its own URL.
        """
        self._pages[page.url] = page

    def fetch(self, url: str) -> FetchedPage | None:
        """Return the canned page for a URL, if any.

        Args:
            url: The URL to fetch.

        Returns:
            The canned page, or None for unknown URLs.
        """
        self.fetched.append(url)
        return self._pages.get(url)
