"""Tavily search adapter."""

from __future__ import annotations

import httpx

from pexon.config.settings import Settings
from pexon.models.research import Source
from pexon.ports.errors import SearchError
from pexon.ports.search import SearchPort

AVAILABLE = True
UNAVAILABLE_REASON = ""


class TavilySearch(SearchPort):
    """Tavily's real search API."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._key = settings.tavily_api_key.get_secret_value() if settings.tavily_api_key else ""

    @property
    def provider(self) -> str:
        return "tavily"

    def search(self, query: str, max_results: int) -> list[Source]:
        """Call Tavily and map results to sources."""
        if not self._key:
            raise SearchError("TAVILY_API_KEY is required for tavily")
        try:
            response = httpx.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": self._key,
                    "query": query,
                    "max_results": max_results,
                    "search_depth": "advanced",
                    "include_answer": False,
                },
                timeout=self._settings.search_timeout_seconds,
            )
            response.raise_for_status()
            data = response.json()
        except Exception as exc:
            raise SearchError(f"tavily request failed: {exc}") from exc
        return [
            Source(
                url=item.get("url", ""),
                title=item.get("title", ""),
                snippet=item.get("content", ""),
                provider=self.provider,
            )
            for item in data.get("results", [])
            if item.get("url")
        ][:max_results]

    def probe(self) -> bool:
        """One-result real search."""
        return bool(self.search("AI Governance Banken", 1))
