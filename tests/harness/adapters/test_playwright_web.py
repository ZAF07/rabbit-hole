"""Issue 04 — the injectable browser-factory: one browser per thread, reused.

No real Chromium runs in CI: a fake browser-factory stands in, so thread
safety (one browser per worker thread, reused across that thread's fetches)
and the navigation-failure path are fast offline assertions.
"""

import threading
from concurrent.futures import ThreadPoolExecutor

from harness.adapters.playwright_web import PlaywrightWebSource


class FakeBrowser:
    """Records the threads it rendered on; models a navigation failure."""

    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.render_threads: list[int] = []
        self.closed = False

    def render(self, url: str, timeout_ms: int):
        self.render_threads.append(threading.get_ident())
        if self.fail:
            return None
        return (f"content of {url}", (f"{url}/cited",))

    def close(self) -> None:
        self.closed = True


def counting_factory(fail: bool = False):
    created: list[tuple[int, FakeBrowser]] = []
    lock = threading.Lock()

    def factory() -> FakeBrowser:
        browser = FakeBrowser(fail=fail)
        with lock:
            created.append((threading.get_ident(), browser))
        return browser

    return factory, created


def test_one_browser_is_created_per_thread_and_reused():
    factory, created = counting_factory()
    web = PlaywrightWebSource(browser_factory=factory)
    for index in range(3):
        assert web.fetch(f"https://example/{index}") is not None
    assert len(created) == 1
    _, browser = created[0]
    assert len(browser.render_threads) == 3


def test_browsers_are_thread_local_no_sharing_across_threads():
    factory, created = counting_factory()
    web = PlaywrightWebSource(browser_factory=factory)
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda i: web.fetch(f"https://example/{i}"), range(40)))
    creating_threads = [tid for tid, _ in created]
    assert len(creating_threads) == len(set(creating_threads))
    for tid, browser in created:
        assert set(browser.render_threads) == {tid}


def test_navigation_failure_returns_none():
    factory, _ = counting_factory(fail=True)
    web = PlaywrightWebSource(browser_factory=factory)
    assert web.fetch("https://unreachable") is None


def test_close_tears_down_every_created_browser():
    factory, created = counting_factory()
    web = PlaywrightWebSource(browser_factory=factory)
    with ThreadPoolExecutor(max_workers=3) as pool:
        list(pool.map(lambda i: web.fetch(f"https://example/{i}"), range(30)))
    web.close()
    assert created
    assert all(browser.closed for _, browser in created)
