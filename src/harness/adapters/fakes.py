"""Deterministic fakes for both ports — the offline test substrate.

With these two fakes plus the in-memory ``ContentGraphRepository`` from
content_graph, the whole pipeline runs end-to-end offline (ADR 0011's
stated payoff). The scripted LLM dispatches on request purpose; tests
register or replace handlers per purpose to steer behavior.
"""

from collections.abc import Callable, Mapping

from harness.ports.llm import LLMPort, LLMRequest
from harness.ports.web_source import FetchedPage, WebSourcePort

Handler = Callable[[LLMRequest], str]


class ScriptedLLM(LLMPort):
    """Purpose-dispatched fake LLM with recordable requests."""

    def __init__(self, handlers: Mapping[str, Handler] | None = None) -> None:
        """Create the fake.

        Args:
            handlers: Initial purpose → handler mapping.
        """
        self._handlers: dict[str, Handler] = dict(handlers or {})
        self.requests: list[LLMRequest] = []

    def on(self, purpose: str, handler: Handler) -> None:
        """Register or replace the handler for one purpose.

        Args:
            purpose: The request purpose to intercept.
            handler: The function producing the response text.
        """
        self._handlers[purpose] = handler

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
