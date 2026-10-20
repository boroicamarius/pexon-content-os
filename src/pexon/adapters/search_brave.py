"""Brave Search adapter."""

from __future__ import annotations

import httpx

from pexon.config.settings import Settings
from pexon.models.research import Source
from pexon.ports.errors import SearchError
from pexon.ports.search import SearchPort

AVAILABLE = True
UNAVAILABLE_REASON = ""


class BraveSearch(SearchPort):
    """Brave Search API adapter."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._key = settings.brave_api_key.get_secret_value() if settings.brave_api_key else ""

    @property
    def provider(self) -> str:
        return "brave"

    def search(self, query: str, max_results: int) -> list[Source]:
        """Call Brave and map web results."""
        if not self._key:
            raise SearchError("BRAVE_API_KEY is required for brave")
        try:
            response = httpx.get(
                "https://api.search.brave.com/res/v1/web/search",
                params={"q": query, "count": max_results, "search_lang": "de"},
                headers={"X-Subscription-Token": self._key, "Accept": "application/json"},
                timeout=self._settings.search_timeout_seconds,
            )
            response.raise_for_status()
            data = response.json()
        except Exception as exc:
            raise SearchError(f"brave request failed: {exc}") from exc
        return [
            Source(
                url=item.get("url", ""),
                title=item.get("title", ""),
                snippet=item.get("description", ""),
                provider=self.provider,
            )
            for item in data.get("web", {}).get("results", [])
            if item.get("url")
        ][:max_results]

    def probe(self) -> bool:
        """One-result real search."""
        return bool(self.search("AI Governance Banken", 1))
