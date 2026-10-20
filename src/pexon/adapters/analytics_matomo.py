"""Matomo analytics adapter."""

from __future__ import annotations

from datetime import UTC, datetime

import httpx

from pexon.config.settings import Settings
from pexon.models.performance import Performance, PerformanceBundle
from pexon.ports.analytics import AnalyticsPort
from pexon.ports.errors import AnalyticsError

AVAILABLE = True
UNAVAILABLE_REASON = ""


class MatomoAnalytics(AnalyticsPort):
    """Matomo Actions.getPageUrl; visits map to clicks and hits to impressions."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    @property
    def provider(self) -> str:
        return "matomo"

    def fetch(
        self, article_id: str, *, window_days: int, page_url: str | None = None
    ) -> PerformanceBundle:
        """Query page-level Matomo actions."""
        if not self._settings.matomo_base_url or not self._settings.matomo_token:
            raise AnalyticsError("MATOMO_BASE_URL and MATOMO_TOKEN are required")
        page = page_url or (article_id if article_id.startswith("http") else "")
        params = {
            "module": "API",
            "method": "Actions.getPageUrl",
            "idSite": self._settings.matomo_site_id,
            "period": "range",
            "date": f"last{window_days}",
            "pageUrl": page,
            "format": "JSON",
            "token_auth": self._settings.matomo_token.get_secret_value(),
        }
        try:
            response = httpx.get(
                f"{self._settings.matomo_base_url.rstrip('/')}/index.php",
                params=params,
                timeout=self._settings.search_timeout_seconds,
            )
            response.raise_for_status()
            data = response.json()
        except Exception as exc:
            raise AnalyticsError(f"matomo query failed: {exc}") from exc
        item = (
            data[0] if isinstance(data, list) and data else data if isinstance(data, dict) else {}
        )
        hits = float(item.get("nb_hits", 0) or 0)
        visits = float(item.get("nb_visits", 0) or 0)
        rows = (
            (
                Performance(
                    article_id=article_id,
                    clicks=visits,
                    impressions=hits,
                    position=0.0,
                    measured_at=datetime.now(UTC),
                    source=self.provider,
                    page_url=page,
                ),
            )
            if hits or visits
            else ()
        )
        return PerformanceBundle(
            article_id=article_id, rows=rows, clicks=visits, impressions=hits, position=0.0
        )

    def probe(self) -> bool:
        """Authenticate against the Matomo API."""
        try:
            response = httpx.get(
                f"{self._settings.matomo_base_url.rstrip('/')}/index.php",
                params={
                    "module": "API",
                    "method": "API.getMatomoVersion",
                    "format": "JSON",
                    "token_auth": self._settings.matomo_token.get_secret_value()
                    if self._settings.matomo_token
                    else "",
                },
                timeout=self._settings.search_timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
            if isinstance(payload, dict):
                return bool(payload.get("value"))
            return bool(payload)
        except Exception as exc:
            raise AnalyticsError(f"matomo probe failed: {exc}") from exc
