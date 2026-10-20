"""SerpAPI Google search adapter."""

from __future__ import annotations

import httpx

from pexon.config.settings import Settings
from pexon.models.research import Source
from pexon.ports.errors import SearchError
from pexon.ports.search import SearchPort

AVAILABLE = True
UNAVAILABLE_REASON = ""


class SerpAPISearch(SearchPort):
    """SerpAPI's real Google SERP endpoint."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._key = settings.serpapi_api_key.get_secret_value() if settings.serpapi_api_key else ""

    @property
    def provider(self) -> str:
        return "serpapi"

    def search(self, query: str, max_results: int) -> list[Source]:
        """Call SerpAPI and map organic results."""
        if not self._key:
            raise SearchError("SERPAPI_API_KEY is required for serpapi")
        try:
            response = httpx.get(
                "https://serpapi.com/search.json",
                params={
                    "engine": "google",
                    "q": query,
                    "api_key": self._key,
                    "num": max_results,
                    "hl": "de",
                    "gl": "de",
                },
                timeout=self._settings.search_timeout_seconds,
            )
            response.raise_for_status()
            data = response.json()
        except Exception as exc:
            raise SearchError(f"serpapi request failed: {exc}") from exc
        return [
            Source(
                url=item.get("link", ""),
                title=item.get("title", ""),
                snippet=item.get("snippet", ""),
                provider=self.provider,
            )
            for item in data.get("organic_results", [])
            if item.get("link")
        ][:max_results]

    def probe(self) -> bool:
        """One-result real search."""
        return bool(self.search("AI Governance Banken", 1))
