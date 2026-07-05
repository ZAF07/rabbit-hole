"""The V1 ``WebSourcePort`` adapter — Playwright fetch, never a search engine.

Renders JS (many sources are not static HTML), returns readable text plus
the page's outbound links for bounded citation-chasing (ADR 0011). The
import is lazy so the harness runs offline (tests, CI) without Playwright
installed; install the ``web`` extra to use this adapter.
"""

from datetime import UTC, datetime

from harness.ports.web_source import FetchedPage, WebSourcePort


class PlaywrightWebSource(WebSourcePort):
    """Fetches pages with a headless Chromium via Playwright."""

    def __init__(self, timeout_ms: int = 15_000) -> None:
        """Configure the adapter.

        Args:
            timeout_ms: Per-navigation timeout.
        """
        self._timeout_ms = timeout_ms

    def fetch(self, url: str) -> FetchedPage | None:
        """Fetch one page's rendered text and outbound links.

        Args:
            url: The URL to fetch.

        Returns:
            The page, or None if navigation failed.

        Raises:
            RuntimeError: If Playwright is not installed (install the
                ``web`` extra: ``uv sync --extra web``).
        """
        try:
            from playwright.sync_api import Error as PlaywrightError
            from playwright.sync_api import sync_playwright
        except ModuleNotFoundError as error:
            raise RuntimeError(
                "PlaywrightWebSource requires the 'web' extra (uv sync --extra web,"
                " then 'uv run playwright install chromium')"
            ) from error

        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                try:
                    page = browser.new_page()
                    page.goto(url, timeout=self._timeout_ms, wait_until="domcontentloaded")
                    content = page.inner_text("body")
                    hrefs = page.eval_on_selector_all(
                        "a[href]", "elements => elements.map(a => a.href)"
                    )
                finally:
                    browser.close()
        except PlaywrightError:
            return None
        outlinks = tuple(
            dict.fromkeys(
                href for href in hrefs if isinstance(href, str) and href.startswith("http")
            )
        )
        return FetchedPage(
            url=url,
            content=content,
            outlinks=outlinks,
            fetched_at=datetime.now(tz=UTC).isoformat(),
        )
