"""Frame 3: competitor intelligence, metric importance, insights and drift."""

from __future__ import annotations

import hashlib
import logging
import math
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC

from pexon.config.prompts import (
    ENGINE_PROMPTS,
    ENGINE_SUMMARY_SCHEMA,
    ENGINE_USER,
    INSIGHTS_SYSTEM,
    INSIGHTS_USER,
    JSON_INSTRUCTION_DE,
    PAGE_RANK_SYSTEM,
    PAGE_RANK_USER,
)
from pexon.config.settings import Settings
from pexon.guards.sanitize import Sanitizer
from pexon.models.prediction import TrainingReport
from pexon.models.research import (
    CompetitorPage,
    EngineAnswer,
    InsightSet,
    PageRankResponse,
    Source,
)
from pexon.models.topic import Topic
from pexon.observability.metrics import MetricsCollector
from pexon.ports.embeddings import EmbeddingsPort
from pexon.ports.search import SearchPort
from pexon.ports.storage import StoragePort
from pexon.services.audit import AuditLog
from pexon.services.drift import DriftMonitor
from pexon.services.gateway import LLMGateway
from pexon.services.learner import Learner

logger = logging.getLogger(__name__)
SearchFactory = Callable[[str], SearchPort]


class IntelligenceService:
    """One service for the complete Intelligence frame."""

    def __init__(
        self,
        settings: Settings,
        search: SearchPort,
        generator: LLMGateway,
        embeddings: EmbeddingsPort,
        storage: StoragePort,
        learner: Learner,
        drift: DriftMonitor,
        audit: AuditLog,
        metrics: MetricsCollector,
        search_factory: SearchFactory,
    ) -> None:
        self._settings = settings
        self._search = search
        self._generator = generator
        self._embeddings = embeddings
        self._storage = storage
        self._learner = learner
        self._drift = drift
        self._audit = audit
        self._metrics = metrics
        self._search_factory = search_factory
        self._sanitizer = Sanitizer(settings)

    def call_providers(self, topic: Topic, run_id: str) -> list[CompetitorPage]:
        """Query the SERP and role-play every configured engine concurrently."""
        queries = [
            topic.name_de,
            f"{topic.name_de} Banken",
        ][: self._settings.competitor_search_queries]
        engines = self._settings.engines
        pages: list[CompetitorPage] = []
        with ThreadPoolExecutor(max_workers=self._settings.intelligence_workers) as pool:
            search_futures = [pool.submit(self._search_query, query, run_id) for query in queries]
            engine_futures = [
                pool.submit(self._engine_answer, topic, engine, run_id) for engine in engines
            ]
            for future in search_futures:
                pages.extend(future.result())
            for future in engine_futures:
                page = future.result()
                if page is not None:
                    pages.append(page)
        if not pages:
            self._audit.emit(run_id, "intelligence_no_pages", {"topic": topic.name_de})
        return pages

    def _search_query(self, query: str, run_id: str) -> list[CompetitorPage]:
        for provider in self._settings.fallback_providers:
            try:
                port = (
                    self._search
                    if provider == self._search.provider
                    else self._search_factory(provider)
                )
                self._metrics.inc("search_calls", {"provider": provider})
                results = port.search(query, self._settings.competitor_top_n)
                if provider != self._settings.search_provider:
                    self._metrics.inc(
                        "provider_fallbacks", {"port": "search", "provider": provider}
                    )
                    self._audit.emit(
                        run_id,
                        "search_fallback",
                        {
                            "query": query,
                            "provider": provider,
                        },
                    )
                return self._to_pages(results, provider)
            except Exception as exc:
                self._audit.emit(
                    run_id,
                    "competitor_search_failed",
                    {
                        "query": query,
                        "provider": provider,
                        "error": str(exc),
                    },
                )
        return []

    def _to_pages(self, sources: list[Source], provider: str) -> list[CompetitorPage]:
        return [
            CompetitorPage(
                id=f"page-{hashlib.sha256(source.url.encode()).hexdigest()[:12]}",
                url=source.url,
                title=source.title,
                provider=provider,
                content=self._sanitizer.clean(source.snippet or source.content).text,
            )
            for source in sources
            if source.url
        ]

    def _engine_answer(self, topic: Topic, engine: str, run_id: str) -> CompetitorPage | None:
        system = ENGINE_PROMPTS.get(engine)
        if not system:
            self._audit.emit(run_id, "engine_prompt_missing", {"engine": engine})
            return None
        query = f"{topic.name_de} für deutsche Banken"
        prompt = ENGINE_USER.format(query=query)
        system = system + "\n" + JSON_INSTRUCTION_DE + ENGINE_SUMMARY_SCHEMA
        try:
            answer = self._generator.structured(
                system,
                prompt,
                EngineAnswer,
                max_tokens=self._settings.engine_answer_max_tokens,
            )
            assert isinstance(answer, EngineAnswer)
        except Exception as exc:
            self._audit.emit(run_id, "engine_answer_failed", {"engine": engine, "error": str(exc)})
            return None
        digest = hashlib.sha256(f"{engine}:{answer.answer_de}".encode()).hexdigest()[:12]
        return CompetitorPage(
            id=f"engine-{digest}",
            url=f"engine://{engine}/{digest}",
            title=f"{engine} Antwort: {topic.name_de}",
            provider=engine,
            content=answer.answer_de,
        )

    def aggregate(self, pages: list[CompetitorPage], run_id: str) -> list[CompetitorPage]:
        """Dedupe by URL, then semantically via embeddings."""
        by_url: dict[str, CompetitorPage] = {}
        for page in pages:
            by_url.setdefault(page.url, page)
        candidates = list(by_url.values())
        if len(candidates) < 2:
            return candidates
        try:
            vectors = self._embeddings.embed(
                [
                    page.content[: self._settings.engine_answer_excerpt_chars] or page.title
                    for page in candidates
                ]
            )
        except Exception as exc:
            self._audit.emit(run_id, "semantic_dedupe_failed", {"error": str(exc)})
            return candidates
        kept: list[CompetitorPage] = []
        kept_indices: list[int] = []
        for index, page in enumerate(candidates):
            duplicate = None
            for kept_index in kept_indices:
                similarity = _cosine(vectors[index], vectors[kept_index])
                if similarity >= self._settings.semantic_dedupe_threshold:
                    duplicate = candidates[kept_index].id
                    break
            if duplicate:
                self._audit.emit(run_id, "semantic_duplicate", {"page": page.id, "of": duplicate})
                kept.append(page.model_copy(update={"duplicate_of": duplicate}))
            else:
                kept.append(page)
                kept_indices.append(index)
        deduped = [page for page in kept if page.duplicate_of is None]
        self._audit.emit(
            run_id,
            "intelligence_aggregated",
            {
                "input": len(pages),
                "deduped": len(deduped),
            },
        )
        return deduped

    def rank_pages(
        self, pages: list[CompetitorPage], topic: Topic, run_id: str
    ) -> list[CompetitorPage]:
        """Ask the LLM for page features and persist the vectors."""
        with ThreadPoolExecutor(max_workers=self._settings.intelligence_workers) as pool:
            ranked = list(pool.map(lambda page: self._rank_one(page, topic, run_id), pages))
        result = [page for page in ranked if page is not None]
        self._audit.emit(run_id, "pages_ranked", {"pages": len(result)})
        return result

    def _rank_one(self, page: CompetitorPage, topic: Topic, run_id: str) -> CompetitorPage | None:
        prompt = PAGE_RANK_USER.format(
            topic=topic.name_de,
            title=page.title,
            url=page.url,
            content=page.content[: self._settings.engine_answer_excerpt_chars],
        )
        try:
            response = self._generator.structured(
                PAGE_RANK_SYSTEM,
                prompt,
                PageRankResponse,
                max_tokens=self._settings.page_rank_max_tokens,
            )
            assert isinstance(response, PageRankResponse)
        except Exception as exc:
            self._audit.emit(run_id, "page_rank_failed", {"page": page.id, "error": str(exc)})
            return None
        features = response.to_features()
        self._storage.write(
            "features",
            {
                "id": f"features-{page.id}",
                "article_id": f"competitor:{page.id}",
                "features_json": features.as_dict(),
                "created_at": _now_iso(),
            },
        )
        return page.model_copy(update={"features": features})

    def modify_importance(self, run_id: str) -> TrainingReport:
        """Fit the learner; this is the only place metric importance changes."""
        report = self._learner.fit(run_id)
        self._audit.emit(
            run_id,
            "metric_importance_updated",
            {
                "trained": report.trained,
                "version": report.version,
                "reason": report.reason,
                "metrics": report.metrics,
            },
        )
        return report

    def extract_insights(
        self, topic: Topic, pages: list[CompetitorPage], run_id: str
    ) -> InsightSet:
        """Compare the strongest competitor profile with our latest draft."""
        top = self.top_page(pages)
        if top is None:
            return InsightSet(insights_de=(), actions_de=())
        last_article = self._storage.latest("articles", order_by="created_at")
        prompt = INSIGHTS_USER.format(
            topic=topic.name_de,
            url=top.url,
            features=top.features.as_dict() if top.features else {},
            last_draft=(last_article or {}).get("body_md", "")[
                : self._settings.engine_answer_excerpt_chars
            ],
        )
        try:
            insights = self._generator.structured(
                INSIGHTS_SYSTEM,
                prompt,
                InsightSet,
                max_tokens=self._settings.insight_max_tokens,
            )
            assert isinstance(insights, InsightSet)
        except Exception as exc:
            self._audit.emit(run_id, "insights_failed", {"error": str(exc)})
            return InsightSet(insights_de=(), actions_de=(), top_competitor_url=top.url)
        insights = insights.model_copy(update={"top_competitor_url": top.url})
        self._audit.emit(
            run_id,
            "insights_extracted",
            {
                "top_competitor": top.url,
                "insights": list(insights.insights_de),
            },
        )
        return insights

    def check_drift(self, run_id: str) -> dict[str, object]:
        """Run PSI/KS detection and return the report."""
        return self._drift.check(run_id)

    @staticmethod
    def top_page(pages: list[CompetitorPage]) -> CompetitorPage | None:
        """Return the strongest page by summed page features."""
        ranked = [page for page in pages if page.features]
        if not ranked:
            return None

        def score(page: CompetitorPage) -> float:
            features = page.features
            return sum(features.as_dict().values()) if features else 0.0

        return max(ranked, key=score)


def _cosine(left: list[float], right: list[float]) -> float:
    if not left or not right:
        return 0.0
    dot = sum(a * b for a, b in zip(left, right, strict=False))
    left_norm = math.sqrt(sum(a * a for a in left)) or 1.0
    right_norm = math.sqrt(sum(b * b for b in right)) or 1.0
    return dot / (left_norm * right_norm)


def _now_iso() -> str:
    from datetime import datetime

    return datetime.now(UTC).isoformat()
