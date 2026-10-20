"""Plausible analytics adapter."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import httpx

from pexon.config.settings import Settings
from pexon.models.performance import Performance, PerformanceBundle
from pexon.ports.analytics import AnalyticsPort
from pexon.ports.errors import AnalyticsError

AVAILABLE = True
UNAVAILABLE_REASON = ""


class PlausibleAnalytics(AnalyticsPort):
    """Plausible Stats API; visitors map to clicks and pageviews to impressions."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    @property
    def provider(self) -> str:
        return "plausible"

    def fetch(
        self, article_id: str, *, window_days: int, page_url: str | None = None
    ) -> PerformanceBundle:
        """Aggregate page metrics for the window."""
        if not self._settings.plausible_site_id or not self._settings.plausible_api_key:
            raise AnalyticsError("PLAUSIBLE_SITE_ID and PLAUSIBLE_API_KEY are required")
        end = date.today()
        start = end - timedelta(days=window_days)
        params: dict[str, str] = {
            "site_id": self._settings.plausible_site_id,
            "period": "custom",
            "date": f"{start.isoformat()},{end.isoformat()}",
            "metrics": "visitors,pageviews",
        }
        if page_url:
            params["filters"] = f"event:page=={page_url}"
        try:
            response = httpx.get(
                f"{self._settings.plausible_base_url.rstrip('/')}/api/v1/stats/aggregate",
                params=params,
                headers={
                    "Authorization": f"Bearer {self._settings.plausible_api_key.get_secret_value()}"
                },
                timeout=self._settings.search_timeout_seconds,
            )
            response.raise_for_status()
            data = response.json()
        except Exception as exc:
            raise AnalyticsError(f"plausible query failed: {exc}") from exc
        metrics = data.get("results", {})
        clicks = float(metrics.get("visitors", {}).get("value", 0) or 0)
        impressions = float(metrics.get("pageviews", {}).get("value", 0) or 0)
        rows = (
            (
                Performance(
                    article_id=article_id,
                    clicks=clicks,
                    impressions=impressions,
                    position=0.0,
                    measured_at=datetime.now(UTC),
                    source=self.provider,
                    page_url=page_url or "",
                ),
            )
            if clicks or impressions
            else ()
        )
        return PerformanceBundle(
            article_id=article_id, rows=rows, clicks=clicks, impressions=impressions, position=0.0
        )

    def probe(self) -> bool:
        """Run a one-day aggregate query."""
        self.fetch("probe", window_days=1)
        return True
