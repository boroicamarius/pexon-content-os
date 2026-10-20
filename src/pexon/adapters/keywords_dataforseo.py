"""DataForSEO keyword-volume adapter."""
from __future__ import annotations

import httpx

from pexon.config.settings import Settings
from pexon.models.portfolio import KeywordDemand
from pexon.ports.errors import ProviderError
from pexon.ports.keywords import KeywordPort

AVAILABLE = True
UNAVAILABLE_REASON = ""


class DataForSeoKeywords(KeywordPort):
    """Reads real Google Ads search volume through DataForSEO."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._password = (
            settings.dataforseo_password.get_secret_value()
            if settings.dataforseo_password else ""
        )

    @property
    def provider(self) -> str:
        return "dataforseo"

    def demand(self, seeds: list[str], limit: int) -> list[KeywordDemand]:
        """Query Google Ads search volume for the seed list."""
        if not self._settings.dataforseo_login or not self._password:
            raise ProviderError("DATAFORSEO_LOGIN and DATAFORSEO_PASSWORD are required")
        if not seeds:
            return []
        payload = [{
            "keywords": seeds[:limit],
            "location_code": self._settings.keyword_location_code,
            "language_code": self._settings.keyword_language_code,
        }]
        try:
            response = httpx.post(
                "https://api.dataforseo.com/v3/keywords_data/google_ads/search_volume/live",
                auth=(self._settings.dataforseo_login, self._password),
                json=payload,
                timeout=self._settings.keyword_timeout_seconds,
            )
            response.raise_for_status()
            data = response.json()
        except Exception as exc:
            raise ProviderError(f"dataforseo query failed: {exc}") from exc
        tasks = data.get("tasks", [])
        result = tasks[0].get("result", []) if tasks else []
        rows = [self._map(item) for item in result if item.get("keyword")]
        return rows[:limit]

    def _map(self, item: dict) -> KeywordDemand:
        competition = item.get("competition")
        difficulty = float(item.get("competition_index") or 0)
        if not difficulty and isinstance(competition, str):
            difficulty = {"LOW": 20.0, "MEDIUM": 50.0, "HIGH": 80.0}.get(competition.upper(), 0.0)
        return KeywordDemand(
            keyword=str(item.get("keyword", "")),
            volume=int(item.get("search_volume") or 0),
            difficulty=min(100.0, max(0.0, difficulty)),
            cpc=float(item.get("cpc") or 0),
            intent="informational",
            funnel_stage="top",
            cluster="",
            source=self.provider,
        )

    def probe(self) -> bool:
        """Query one keyword through the real endpoint."""
        self.demand(["AI Governance Banken"], 1)
        return True
