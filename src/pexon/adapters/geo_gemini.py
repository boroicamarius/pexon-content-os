"""Real Gemini Google-Search grounding visibility adapter."""
from __future__ import annotations

from datetime import UTC, datetime

import httpx

from pexon.config.settings import Settings
from pexon.models.geo import GeoQueryResult, GeoReport
from pexon.ports.errors import ProviderError
from pexon.ports.geo import GeoPort

AVAILABLE = True
UNAVAILABLE_REASON = ""


class GeminiGeo(GeoPort):
    """Uses Gemini grounded with Google Search and reads grounding citations."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._key = settings.geo_gemini_api_key.get_secret_value() if settings.geo_gemini_api_key else ""

    @property
    def provider(self) -> str:
        return "gemini"

    def measure(self, queries: list[str], *, brand: str, domain: str,
                topic_id: str, article_id: str | None = None) -> GeoReport:
        if not self._key:
            raise ProviderError("GEO_GEMINI_API_KEY is required for gemini GEO")
        results: list[GeoQueryResult] = []
        for query in queries:
            try:
                response = httpx.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/"
                    f"{self._settings.geo_gemini_model}:generateContent",
                    headers={"x-goog-api-key": self._key, "content-type": "application/json"},
                    json={
                        "contents": [{"role": "user", "parts": [{"text": query}]}],
                        "tools": [{"google_search": {}}],
                        "generationConfig": {
                            "maxOutputTokens": self._settings.engine_answer_max_tokens,
                        },
                    },
                    timeout=self._settings.geo_timeout_seconds,
                )
                response.raise_for_status()
                data = response.json()
            except Exception as exc:
                raise ProviderError(f"gemini GEO query failed: {exc}") from exc
            answer, citations = _parse_response(data)
            results.append(_result(self.provider, query, answer, citations, brand, domain))
        return _report(topic_id, article_id, brand, domain, self.provider, results)

    def probe(self) -> bool:
        """One real grounded query."""
        self.measure(["AI Governance deutsche Banken"], brand=self._settings.geo_brand_name,
                     domain=self._settings.geo_domain, topic_id="probe")
        return True


def _parse_response(data: dict) -> tuple[str, tuple[str, ...]]:
    candidates = data.get("candidates", [])
    if not candidates:
        return "", ()
    candidate = candidates[0]
    parts = candidate.get("content", {}).get("parts", [])
    answer = "\n".join(str(part.get("text", "")) for part in parts)
    citations: list[str] = []
    for chunk in candidate.get("groundingMetadata", {}).get("groundingChunks", []):
        uri = chunk.get("web", {}).get("uri")
        if uri:
            citations.append(str(uri))
    return answer, tuple(dict.fromkeys(citations))


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
