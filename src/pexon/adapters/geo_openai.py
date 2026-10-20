"""Real OpenAI web-search visibility adapter."""
from __future__ import annotations

from datetime import UTC, datetime

import httpx

from pexon.config.settings import Settings
from pexon.models.geo import GeoQueryResult, GeoReport
from pexon.ports.errors import ProviderError
from pexon.ports.geo import GeoPort

AVAILABLE = True
UNAVAILABLE_REASON = ""


class OpenAIGeo(GeoPort):
    """Uses the Responses API with the web_search tool and reads URL citations."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._key = settings.geo_openai_api_key.get_secret_value() if settings.geo_openai_api_key else ""

    @property
    def provider(self) -> str:
        return "openai"

    def measure(self, queries: list[str], *, brand: str, domain: str,
                topic_id: str, article_id: str | None = None) -> GeoReport:
        if not self._key:
            raise ProviderError("GEO_OPENAI_API_KEY is required for openai GEO")
        results: list[GeoQueryResult] = []
        for query in queries:
            try:
                response = httpx.post(
                    "https://api.openai.com/v1/responses",
                    headers={"Authorization": f"Bearer {self._key}",
                             "content-type": "application/json"},
                    json={
                        "model": self._settings.geo_openai_model,
                        "input": query,
                        "tools": [{"type": "web_search"}],
                        "max_output_tokens": self._settings.engine_answer_max_tokens,
                    },
                    timeout=self._settings.geo_timeout_seconds,
                )
                response.raise_for_status()
                data = response.json()
            except Exception as exc:
                raise ProviderError(f"openai GEO query failed: {exc}") from exc
            answer, citations = _parse_response(data)
            results.append(_result(self.provider, query, answer, citations, brand, domain))
        return _report(topic_id, article_id, brand, domain, self.provider, results)

    def probe(self) -> bool:
        """One real web-search query."""
        self.measure(["AI Governance deutsche Banken"], brand=self._settings.geo_brand_name,
                     domain=self._settings.geo_domain, topic_id="probe")
        return True


def _parse_response(data: dict) -> tuple[str, tuple[str, ...]]:
    texts: list[str] = []
    citations: list[str] = []
    for item in data.get("output", []):
        for content in item.get("content", []):
            if content.get("type") in {"output_text", "text"}:
                texts.append(str(content.get("text", "")))
            for annotation in content.get("annotations", []):
                url = annotation.get("url")
                if url:
                    citations.append(str(url))
    return "\n".join(texts), tuple(dict.fromkeys(citations))


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
