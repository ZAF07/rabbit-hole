"""The V1 ``WebSourcePort`` adapter — Playwright fetch, never a search engine.

Renders JS (many sources are not static HTML), returns readable text plus
the page's outbound links so the Researcher can navigate cited outlinks
toward primary sources (ADR 0011). The import is lazy so the harness runs
offline (tests, CI) without Playwright installed; install the ``web`` extra
to use this adapter.

Playwright launches a browser per fetch and its sync API is not freely
thread-safe, so browser creation sits behind an **injectable
browser-factory** with a **thread-local cache**: one browser per worker
thread, reused across that thread's fetches, torn down by ``close`` with the
pool (ADR 0016 Decision 6). The public ``fetch`` surface is unchanged.
"""

import threading
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from harness.ports.web_source import FetchedPage, WebSourcePort

BrowserFactory = Callable[[], Any]


class _OwnedBrowser:
    """A real Playwright browser plus its manager; owns rendering + teardown.

    The rendering error boundary lives here (not in the adapter), so the
    adapter's ``fetch`` stays free of any Playwright import and a fake
    browser can model a navigation failure by returning None.
    """

    def __init__(self, manager: Any, browser: Any) -> None:
        """Wrap a started Playwright manager and its launched browser.

        Args:
            manager: The started ``sync_playwright`` manager.
            browser: The launched Chromium browser.
        """
        self._manager = manager
        self._browser = browser

    def render(self, url: str, timeout_ms: int) -> tuple[str, tuple[str, ...]] | None:
        """Render one page to text + outbound links, or None on failure.

        Args:
            url: The URL to render.
            timeout_ms: Per-navigation timeout.

        Returns:
            ``(content, outlinks)``, or None if navigation failed.
        """
        from playwright.sync_api import Error as PlaywrightError

        try:
            page = self._browser.new_page()
            try:
                page.goto(url, timeout=timeout_ms, wait_until="domcontentloaded")
                content = page.inner_text("body")
                hrefs = page.eval_on_selector_all(
                    "a[href]", "elements => elements.map(a => a.href)"
                )
            finally:
                page.close()
        except PlaywrightError:
            return None
        outlinks = tuple(
            dict.fromkeys(
                href for href in hrefs if isinstance(href, str) and href.startswith("http")
            )
        )
        return content, outlinks

    def close(self) -> None:
        """Close the browser and stop its Playwright manager."""
        self._browser.close()
        self._manager.stop()


def _default_browser_factory() -> _OwnedBrowser:
    """Launch a headless Chromium behind an owned Playwright manager.

    Returns:
        The owned browser.

    Raises:
        RuntimeError: If Playwright is not installed (install the ``web``
            extra: ``uv sync --extra web``).
    """
    try:
        from playwright.sync_api import sync_playwright
    except ModuleNotFoundError as error:
        raise RuntimeError(
            "PlaywrightWebSource requires the 'web' extra (uv sync --extra web,"
            " then 'uv run playwright install chromium')"
        ) from error

    manager = sync_playwright().start()
    browser = manager.chromium.launch(headless=True)
    return _OwnedBrowser(manager, browser)


class PlaywrightWebSource(WebSourcePort):
    """Fetches pages with a headless Chromium via a thread-local browser."""

    def __init__(
        self, timeout_ms: int = 15_000, *, browser_factory: BrowserFactory | None = None
    ) -> None:
        """Configure the adapter.

        Args:
            timeout_ms: Per-navigation timeout.
            browser_factory: Builds one browser handle (a ``render``/``close``
                object); defaults to a real Playwright Chromium. Injected in
                tests so no real Chromium runs in CI.
        """
        self._timeout_ms = timeout_ms
        self._browser_factory = browser_factory or _default_browser_factory
        self._local = threading.local()
        self._browsers: list[Any] = []
        self._lock = threading.Lock()

    def fetch(self, url: str) -> FetchedPage | None:
        """Fetch one page's rendered text and outbound links.

        Args:
            url: The URL to fetch.

        Returns:
            The page, or None if navigation failed.
        """
        rendered = self._browser().render(url, self._timeout_ms)
        if rendered is None:
            return None
        content, outlinks = rendered
        return FetchedPage(
            url=url,
            content=content,
            outlinks=outlinks,
            fetched_at=datetime.now(tz=UTC).isoformat(),
        )

    def close(self) -> None:
        """Tear down every browser this adapter created (called with the pool)."""
        with self._lock:
            browsers = list(self._browsers)
            self._browsers.clear()
        for browser in browsers:
            browser.close()

    def _browser(self) -> Any:
        """Return the calling thread's browser, creating it once on first use.

        Returns:
            The thread-local browser handle.
        """
        browser = getattr(self._local, "browser", None)
        if browser is None:
            browser = self._browser_factory()
            self._local.browser = browser
            with self._lock:
                self._browsers.append(browser)
        return browser
