"""Plain httpx + stdlib readability fetch adapter."""

from __future__ import annotations

import httpx

from pexon.adapters._html_text import html_to_text
from pexon.config.settings import Settings
from pexon.models.research import FetchedPage
from pexon.ports.errors import FetchError
from pexon.ports.fetch import FetchPort

AVAILABLE = True
UNAVAILABLE_REASON = ""


class HttpxFetcher(FetchPort):
    """Fetch raw HTTP and extract text with the standard library."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    @property
    def provider(self) -> str:
        return "httpx"

    def fetch(self, url: str) -> FetchedPage:
        """Fetch and normalise one page."""
        try:
            response = httpx.get(
                url,
                headers={"User-Agent": self._settings.fetch_user_agent},
                timeout=self._settings.fetch_timeout_seconds,
                follow_redirects=True,
            )
            response.raise_for_status()
        except Exception as exc:
            raise FetchError(f"httpx fetch failed for {url}: {exc}") from exc
        title, text = html_to_text(response.text)
        text = text.strip()
        if len(text) < self._settings.fetch_min_chars:
            raise FetchError(f"insufficient readable text for {url}: {len(text)} chars")
        return FetchedPage(
            url=str(response.url),
            title=title,
            content=text[: self._settings.fetch_max_chars],
            status_code=response.status_code,
            content_type=response.headers.get("content-type", ""),
            truncated=len(text) > self._settings.fetch_max_chars,
        )

    def probe(self) -> bool:
        """Check the configured probe page over a real HTTP request."""
        try:
            response = httpx.get(
                self._settings.drill_fetch_url,
                headers={"User-Agent": self._settings.fetch_user_agent},
                timeout=self._settings.fetch_timeout_seconds,
                follow_redirects=True,
            )
            return response.status_code < 400
        except Exception as exc:
            raise FetchError(f"fetch probe failed: {exc}") from exc
