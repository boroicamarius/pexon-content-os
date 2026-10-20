"""Trafilatura fetch adapter with a real stdlib extraction fallback."""

from __future__ import annotations

import logging

import httpx

from pexon.adapters._html_text import html_to_text
from pexon.config.settings import Settings
from pexon.models.research import FetchedPage
from pexon.ports.errors import FetchError
from pexon.ports.fetch import FetchPort

try:
    import trafilatura

    _HAS_TRAFILATURA = True
except ImportError:
    trafilatura = None  # type: ignore[assignment]
    _HAS_TRAFILATURA = False

logger = logging.getLogger(__name__)
AVAILABLE = True
UNAVAILABLE_REASON = ""


class TrafilaturaFetcher(FetchPort):
    """Fetch with httpx and extract main content with trafilatura."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    @property
    def provider(self) -> str:
        return "trafilatura"

    def fetch(self, url: str) -> FetchedPage:
        """Fetch and extract one page."""
        try:
            response = httpx.get(
                url,
                headers={
                    "User-Agent": self._settings.fetch_user_agent,
                    "Accept-Language": "de-DE,de;q=0.9,en;q=0.5",
                },
                timeout=self._settings.fetch_timeout_seconds,
                follow_redirects=True,
            )
            response.raise_for_status()
        except Exception as exc:
            raise FetchError(f"fetch failed for {url}: {exc}") from exc
        content_type = response.headers.get("content-type", "")
        title, text = "", response.text
        if "html" in content_type or response.text.lstrip().startswith("<"):
            title, text = html_to_text(response.text)
            if _HAS_TRAFILATURA:
                try:
                    extracted = trafilatura.extract(
                        response.text,
                        include_comments=False,
                        include_tables=True,
                        favor_recall=True,
                    )
                except Exception:
                    extracted = None
                if extracted and len(extracted) > len(text) // 2:
                    text = extracted
        text = text.strip()
        if len(text) < self._settings.fetch_min_chars:
            raise FetchError(f"insufficient readable text for {url}: {len(text)} chars")
        truncated = len(text) > self._settings.fetch_max_chars
        return FetchedPage(
            url=str(response.url),
            title=title,
            content=text[: self._settings.fetch_max_chars],
            status_code=response.status_code,
            content_type=content_type,
            truncated=truncated,
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
