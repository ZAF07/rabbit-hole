"""The web-sourcing port — fetch/navigate, never a search engine (ADR 0011).

The surface is deliberately ``fetch(url)`` only: it returns readable content
plus the page's outbound links, so the Researcher can citation-chase from
recalled hub pages to the primary sources they cite. There is no
``search(query)`` in V1; a SERP adapter may add one later behind this same
port without touching the corroboration bar.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class FetchedPage:
    """One fetched page's readable content and outbound links.

    Attributes:
        url: The fetched URL.
        content: The page's readable text content.
        outlinks: The page's outbound (cited) links, for bounded chasing.
        fetched_at: ISO timestamp of retrieval.
    """

    url: str
    content: str
    outlinks: tuple[str, ...] = ()
    fetched_at: str = ""


class WebSourcePort(ABC):
    """Fetch seam for the Researcher; no query-based discovery in V1."""

    @abstractmethod
    def fetch(self, url: str) -> FetchedPage | None:
        """Fetch one page's readable content and outbound links.

        Args:
            url: The URL to fetch.

        Returns:
            The page, or None if it could not be retrieved.
        """
