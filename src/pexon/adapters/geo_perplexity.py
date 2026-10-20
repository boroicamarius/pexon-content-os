"""Real Perplexity answer-engine visibility adapter."""
from __future__ import annotations

from datetime import UTC, datetime

import httpx

from pexon.config.settings import Settings
from pexon.models.geo import GeoQueryResult, GeoReport
from pexon.ports.errors import ProviderError
from pexon.ports.geo import GeoPort

AVAILABLE = True
UNAVAILABLE_REASON = ""


class PerplexityGeo(GeoPort):
    """Queries Perplexity's real Sonar endpoint and records citations."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._key = settings.perplexity_api_key.get_secret_value() if settings.perplexity_api_key else ""

    @property
    def provider(self) -> str:
        return "perplexity"

    def measure(self, queries: list[str], *, brand: str, domain: str,
                topic_id: str, article_id: str | None = None) -> GeoReport:
        if not self._key:
            raise ProviderError("PERPLEXITY_API_KEY is required for GEO")
        results: list[GeoQueryResult] = []
        for query in queries:
            try:
                response = httpx.post(
                    "https://api.perplexity.ai/chat/completions",
                    headers={"Authorization": f"Bearer {self._key}",
                             "content-type": "application/json"},
                    json={
                        "model": self._settings.geo_perplexity_model,
                        "messages": [{"role": "user", "content": query}],
                        "max_tokens": self._settings.engine_answer_max_tokens,
                    },
                    timeout=self._settings.geo_timeout_seconds,
                )
                response.raise_for_status()
                data = response.json()
            except Exception as exc:
                raise ProviderError(f"perplexity GEO query failed: {exc}") from exc
            answer = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            citations = tuple(str(url) for url in data.get("citations", []) if url)
            results.append(_result(self.provider, query, answer, citations, brand, domain))
        return _report(topic_id, article_id, brand, domain, self.provider, results)

    def probe(self) -> bool:
        """One real one-query visibility call."""
        self.measure(["AI Governance deutsche Banken"], brand=self._settings.geo_brand_name,
                     domain=self._settings.geo_domain, topic_id="probe")
        return True


def _result(engine: str, query: str, answer: str, citations: tuple[str, ...],
            brand: str, domain: str) -> GeoQueryResult:
    joined = " ".join([answer, *citations]).lower()
    return GeoQueryResult(
        engine=engine, query=query, answer_excerpt=answer[:3500], citation_urls=citations,
        brand_mentioned=brand.lower() in joined,
        domain_cited=domain.lower() in joined,
        measured_at=datetime.now(UTC),
    )


def _report(topic_id: str, article_id: str | None, brand: str, domain: str,
            provider: str, results: list[GeoQueryResult]) -> GeoReport:
    count = len(results) or 1
    return GeoReport(
        topic_id=topic_id, article_id=article_id, brand=brand, domain=domain,
        provider=provider, enabled=True, results=tuple(results),
        mention_rate=sum(1 for r in results if r.brand_mentioned) / count,
        citation_rate=sum(1 for r in results if r.domain_cited) / count,
    )
