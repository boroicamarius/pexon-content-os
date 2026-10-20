"""Google Search Console analytics adapter."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from urllib.parse import quote

import httpx

from pexon.config.settings import Settings
from pexon.models.performance import Performance, PerformanceBundle
from pexon.ports.analytics import AnalyticsPort
from pexon.ports.errors import AnalyticsError

try:
    from google.auth.transport.requests import Request as GoogleRequest
    from google.oauth2 import service_account

    _HAS_GOOGLE_AUTH = True
except ImportError:
    service_account = None  # type: ignore[assignment]
    GoogleRequest = None  # type: ignore[assignment]
    _HAS_GOOGLE_AUTH = False

AVAILABLE = True
UNAVAILABLE_REASON = ""
_SCOPE = "https://www.googleapis.com/auth/webmasters.readonly"


class GscAnalytics(AnalyticsPort):
    """Search Console Search Analytics API with OAuth credentials."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._token: str | None = None

    @property
    def provider(self) -> str:
        return "gsc"

    def _access_token(self) -> str:
        if self._settings.gsc_access_token:
            return self._settings.gsc_access_token.get_secret_value()
        if self._token:
            return self._token
        if _HAS_GOOGLE_AUTH and self._settings.gsc_service_account_json:
            try:
                credentials = service_account.Credentials.from_service_account_file(
                    self._settings.gsc_service_account_json, scopes=[_SCOPE]
                )
                credentials.refresh(GoogleRequest())
                self._token = credentials.token
                return self._token
            except Exception as exc:
                raise AnalyticsError(f"GSC service-account auth failed: {exc}") from exc
        if self._settings.gsc_refresh_token and self._settings.gsc_client_id:
            try:
                response = httpx.post(
                    "https://oauth2.googleapis.com/token",
                    data={
                        "client_id": self._settings.gsc_client_id,
                        "client_secret": self._settings.gsc_client_secret.get_secret_value()
                        if self._settings.gsc_client_secret
                        else "",
                        "refresh_token": self._settings.gsc_refresh_token.get_secret_value(),
                        "grant_type": "refresh_token",
                    },
                    timeout=self._settings.search_timeout_seconds,
                )
                response.raise_for_status()
                self._token = response.json()["access_token"]
                return self._token
            except Exception as exc:
                raise AnalyticsError(f"GSC refresh-token auth failed: {exc}") from exc
        raise AnalyticsError("GSC needs GSC_SERVICE_ACCOUNT_JSON or GSC_REFRESH_TOKEN")

    def fetch(
        self, article_id: str, *, window_days: int, page_url: str | None = None
    ) -> PerformanceBundle:
        """Query page-level Search Console metrics."""
        if not self._settings.gsc_site_url:
            raise AnalyticsError("GSC_SITE_URL is required")
        token = self._access_token()
        end = date.today()
        start = end - timedelta(days=window_days)
        body: dict[str, object] = {
            "startDate": start.isoformat(),
            "endDate": end.isoformat(),
            "dimensions": ["page"],
            "rowLimit": 250,
        }
        page = page_url or (article_id if article_id.startswith("http") else "")
        if page:
            body["dimensionFilterGroups"] = [
                {"filters": [{"dimension": "page", "operator": "equals", "expression": page}]}
            ]
        site = quote(self._settings.gsc_site_url, safe="")
        try:
            response = httpx.post(
                f"https://searchconsole.googleapis.com/webmasters/v3/sites/{site}/searchAnalytics/query",
                headers={"Authorization": f"Bearer {token}"},
                json=body,
                timeout=self._settings.search_timeout_seconds,
            )
            response.raise_for_status()
            data = response.json()
        except Exception as exc:
            raise AnalyticsError(f"GSC query failed: {exc}") from exc
        rows: list[Performance] = []
        now = datetime.now(UTC)
        for item in data.get("rows", []):
            keys = item.get("keys", [])
            rows.append(
                Performance(
                    article_id=article_id,
                    clicks=float(item.get("clicks", 0)),
                    impressions=float(item.get("impressions", 0)),
                    position=float(item.get("position", 0)),
                    measured_at=now,
                    source=self.provider,
                    page_url=keys[0] if keys else (page or ""),
                )
            )
        clicks = sum(r.clicks for r in rows)
        impressions = sum(r.impressions for r in rows)
        weighted = sum(r.position * max(r.impressions, 1) for r in rows)
        return PerformanceBundle(
            article_id=article_id,
            rows=tuple(rows),
            clicks=clicks,
            impressions=impressions,
            position=weighted / max(impressions, 1),
        )

    def probe(self) -> bool:
        """Acquire a token and run a one-row query."""
        self.fetch("probe", window_days=1)
        return True
