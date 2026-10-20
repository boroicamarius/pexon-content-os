"""Measure real AI-answer visibility for a topic or published article."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from pexon.config.prompts import GEO_QUERY_TEMPLATES
from pexon.config.settings import Settings
from pexon.models.geo import GeoReport
from pexon.ports.geo import GeoPort
from pexon.ports.storage import StoragePort
from pexon.services.audit import AuditLog


class GeoService:
    """Runs real answer-engine queries and records brand/domain citations."""

    def __init__(
        self, settings: Settings, geo: GeoPort, storage: StoragePort, audit: AuditLog
    ) -> None:
        self._settings = settings
        self._geo = geo
        self._storage = storage
        self._audit = audit

    def queries(self, topic_name: str) -> list[str]:
        """Build the German query set used for visibility measurement."""
        queries = [template.format(topic=topic_name) for template in GEO_QUERY_TEMPLATES]
        return queries[: self._settings.geo_query_count]

    def measure_topic(
        self, topic_id: str, topic_name: str, run_id: str, article_id: str | None = None
    ) -> GeoReport | None:
        """Measure configured engines and persist one row per query result."""
        if not self._settings.geo_enabled:
            self._audit.emit(run_id, "geo_disabled", {"reason": "GEO_PROVIDER=none"})
            return None
        domain = self._settings.effective_geo_domain
        queries = self.queries(topic_name)
        try:
            report = self._geo.measure(
                queries,
                brand=self._settings.geo_brand_name,
                domain=domain,
                topic_id=topic_id,
                article_id=article_id,
            )
        except Exception as exc:
            self._audit.emit(
                run_id,
                "geo_measure_failed",
                {
                    "provider": self._geo.provider,
                    "error": str(exc),
                },
            )
            return None
        for result in report.results:
            self._storage.write(
                "geo_visibility",
                {
                    "id": f"geo-{uuid.uuid4().hex[:12]}",
                    "run_id": run_id,
                    "article_id": article_id,
                    "topic_id": topic_id,
                    "engine": result.engine,
                    "query": result.query,
                    "brand_mentioned": result.brand_mentioned,
                    "domain_cited": result.domain_cited,
                    "citations_json": list(result.citation_urls),
                    "answer_excerpt": result.answer_excerpt,
                    "measured_at": (result.measured_at or datetime.now(UTC)).isoformat(),
                    "provider": report.provider,
                },
            )
        self._audit.emit(
            run_id,
            "geo_measured",
            {
                "provider": report.provider,
                "queries": len(report.results),
                "mention_rate": report.mention_rate,
                "citation_rate": report.citation_rate,
                "brand": report.brand,
                "domain": report.domain,
            },
        )
        return report
