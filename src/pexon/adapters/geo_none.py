"""Explicit no-GEO-measurement adapter."""
from __future__ import annotations

from pexon.config.settings import Settings
from pexon.models.geo import GeoReport
from pexon.ports.geo import GeoPort

AVAILABLE = True
UNAVAILABLE_REASON = ""


class NoGeo(GeoPort):
    """Records that GEO measurement is disabled; never fabricates visibility."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    @property
    def provider(self) -> str:
        return "none"

    def measure(self, queries: list[str], *, brand: str, domain: str,
                topic_id: str, article_id: str | None = None) -> GeoReport:
        """Return a disabled report with no observations."""
        return GeoReport(
            topic_id=topic_id, article_id=article_id, brand=brand, domain=domain,
            provider=self.provider, enabled=False,
        )

    def probe(self) -> bool:
        """No external dependency."""
        return True
