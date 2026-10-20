"""Frame 1: deep research, verified extraction and frozen ground truth."""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

from pexon.config.prompts import (
    FACT_VERIFY_SYSTEM,
    FACT_VERIFY_USER,
    PROMPT_VERSIONS,
    RESEARCH_EXTRACT_SYSTEM,
    RESEARCH_EXTRACT_USER,
    RESEARCH_QUERY_TEMPLATES,
)
from pexon.config.settings import Settings
from pexon.guards.sanitize import Sanitizer
from pexon.models.gate import FactVerdict
from pexon.models.research import (
    ExtractionResult,
    Fact,
    ResearchSnapshot,
    Source,
)
from pexon.models.topic import Topic
from pexon.observability.metrics import MetricsCollector
from pexon.ports.cache import CachePort
from pexon.ports.fetch import FetchPort
from pexon.ports.search import SearchPort
from pexon.ports.storage import StoragePort
from pexon.services.audit import AuditLog
from pexon.services.gateway import LLMGateway

logger = logging.getLogger(__name__)
SearchFactory = Callable[[str], SearchPort]


class ResearchService:
    """One service for the complete Research frame."""

    def __init__(
        self,
        settings: Settings,
        search: SearchPort,
        fetch: FetchPort,
        generator: LLMGateway,
        judge: LLMGateway,
        cache: CachePort,
        storage: StoragePort,
        audit: AuditLog,
        metrics: MetricsCollector,
        search_factory: SearchFactory,
    ) -> None:
        self._settings = settings
        self._search = search
        self._fetch = fetch
        self._generator = generator
        self._judge = judge
        self._cache = cache
        self._storage = storage
        self._audit = audit
        self._metrics = metrics
        self._search_factory = search_factory
        self._sanitizer = Sanitizer(settings)

    def deep_research(self, topic: Topic, run_id: str) -> list[Source]:
        """Run parallel searches through the primary provider and fallback chain."""
        queries = self._queries(topic)
        with ThreadPoolExecutor(max_workers=self._settings.research_workers) as pool:
            batches = list(pool.map(lambda q: self._safe_search(q, run_id), queries))
        seen: set[str] = set()
        sources: list[Source] = []
        for batch in batches:
            for source in batch:
                if source.url and source.url not in seen:
                    seen.add(source.url)
                    sources.append(source)
        if not sources:
            raise RuntimeError("research produced no sources")
        self._storage.write(
            "topics",
            {
                "id": topic.id,
                "name_de": topic.name_de,
                "bank_segment": topic.bank_segment,
                "created_at": datetime.now(UTC).isoformat(),
            },
        )
        self._audit.emit(
            run_id,
            "research_search_complete",
            {
                "queries": len(queries),
                "sources": len(sources),
            },
        )
        return sources

    def _queries(self, topic: Topic) -> list[str]:
        generated = [template.format(topic=topic.name_de) for template in RESEARCH_QUERY_TEMPLATES]
        queries = list(topic.queries) + generated
        unique = list(dict.fromkeys(q.strip() for q in queries if q.strip()))
        return unique[: self._settings.research_query_count]

    def _safe_search(self, query: str, run_id: str) -> list[Source]:
        try:
            return self._search_with_fallback(query, run_id)
        except Exception as exc:
            self._audit.emit(run_id, "research_query_failed", {"query": query, "error": str(exc)})
            return []

    def _search_with_fallback(self, query: str, run_id: str) -> list[Source]:
        errors: list[str] = []
        for index, provider in enumerate(self._settings.fallback_providers):
            try:
                port = (
                    self._search
                    if provider == self._search.provider
                    else self._search_factory(provider)
                )
                self._metrics.inc("search_calls", {"provider": provider})
                results = port.search(query, self._settings.search_results_per_query)
                if index > 0:
                    self._metrics.inc(
                        "provider_fallbacks", {"port": "search", "provider": provider}
                    )
                    self._audit.emit(
                        run_id,
                        "search_fallback",
                        {
                            "query": query,
                            "provider": provider,
                            "errors": errors,
                        },
                    )
                return results
            except Exception as exc:
                errors.append(f"{provider}: {exc}")
                self._audit.emit(
                    run_id,
                    "search_provider_failed",
                    {
                        "query": query,
                        "provider": provider,
                        "error": str(exc),
                    },
                )
        raise RuntimeError(f"all search providers failed for {query!r}: {errors}")

    def fetch_sources(self, sources: list[Source], run_id: str) -> list[Source]:
        """Fetch, sanitize and retain the top N readable sources."""
        candidates = sources[: self._settings.fetch_top_n]
        with ThreadPoolExecutor(max_workers=self._settings.fetch_workers) as pool:
            fetched = list(pool.map(lambda source: self._fetch_one(source, run_id), candidates))
        readable = [source for source in fetched if source and source.content]
        if not readable:
            raise RuntimeError("no source could be fetched")
        self._audit.emit(
            run_id,
            "research_fetch_complete",
            {
                "attempted": len(candidates),
                "readable": len(readable),
            },
        )
        return readable

    def _fetch_one(self, source: Source, run_id: str) -> Source | None:
        try:
            page = self._fetch.fetch(source.url)
            clean = self._sanitizer.clean(page.content)
            if clean.removed_patterns:
                self._audit.emit(
                    run_id,
                    "prompt_injection_removed",
                    {
                        "url": source.url,
                        "patterns": clean.removed_patterns,
                    },
                )
            self._metrics.inc("fetch_ok", {"provider": self._fetch.provider})
            return source.model_copy(
                update={
                    "title": page.title or source.title,
                    "content": clean.text,
                    "fetched_at": page.fetched_at,
                    "status": "fetched",
                }
            )
        except Exception as exc:
            self._metrics.inc("fetch_fail", {"provider": self._fetch.provider})
            self._audit.emit(run_id, "fetch_failed", {"url": source.url, "error": str(exc)})
            return None

    def extract_ground_truth(
        self, topic: Topic, sources: list[Source], run_id: str
    ) -> ResearchSnapshot:
        """Extract facts, verify each against its source and freeze the snapshot."""
        prompt = RESEARCH_EXTRACT_USER.format(
            topic=topic.name_de,
            segment=topic.bank_segment,
            sources=self._source_context(sources),
            max_facts=self._settings.research_max_facts,
        )
        extracted = self._generator.structured(
            RESEARCH_EXTRACT_SYSTEM,
            prompt,
            ExtractionResult,
            max_tokens=self._settings.draft_max_tokens,
        )
        assert isinstance(extracted, ExtractionResult)
        verified = self._verify_facts(topic, extracted, sources, run_id)
        references = tuple(
            dict.fromkeys([*extracted.references, *(fact.source_url for fact in verified)])
        )
        snapshot_hash = self._hash(topic, sources, verified)
        snapshot = ResearchSnapshot(
            topic_id=topic.id,
            sources=tuple(sources),
            facts=tuple(verified),
            references=references,
            snapshot_hash=snapshot_hash,
        )
        row = {
            "id": f"snapshot-{snapshot_hash[:16]}",
            "topic_id": topic.id,
            "snapshot_hash": snapshot_hash,
            "facts_json": [fact.model_dump(mode="json") for fact in snapshot.facts],
            "sources_json": [source.model_dump(mode="json") for source in snapshot.sources],
            "created_at": snapshot.created_at.isoformat(),
        }
        self._storage.write("research_snapshots", row)
        self._cache.set_json(f"research_{snapshot_hash}", snapshot.model_dump(mode="json"))
        self._audit.emit(
            run_id,
            "ground_truth_frozen",
            {
                "snapshot_hash": snapshot_hash,
                "facts": len(verified),
                "dropped": len(extracted.facts) - len(verified),
                "sources": len(sources),
                "prompt_version": PROMPT_VERSIONS["research_extract"],
            },
        )
        return snapshot

    def _verify_facts(
        self, topic: Topic, extracted: ExtractionResult, sources: list[Source], run_id: str
    ) -> list[Fact]:
        by_url = {source.url: source for source in sources}
        facts: list[Fact] = []
        for index, item in enumerate(extracted.facts):
            source = by_url.get(item.source_url)
            if source is None or not source.content:
                self._audit.emit(
                    run_id,
                    "fact_dropped",
                    {
                        "claim": item.claim_de,
                        "reason": "source not fetched",
                    },
                )
                continue
            prompt = FACT_VERIFY_USER.format(
                claim=item.claim_de,
                url=item.source_url,
                quote=item.quote_de,
                source=source.content[: self._settings.fact_verification_max_chars],
            )
            try:
                verdict = self._judge.structured(
                    FACT_VERIFY_SYSTEM,
                    prompt,
                    FactVerdict,
                    max_tokens=self._settings.llm_max_tokens,
                )
                assert isinstance(verdict, FactVerdict)
            except Exception as exc:
                self._audit.emit(
                    run_id,
                    "fact_verification_failed",
                    {
                        "claim": item.claim_de,
                        "error": str(exc),
                    },
                )
                continue
            accepted = verdict.present and verdict.confidence >= self._settings.fact_confidence_min
            if accepted:
                facts.append(
                    Fact(
                        id=f"fact-{index + 1}",
                        claim_de=item.claim_de,
                        source_url=item.source_url,
                        quote_de=item.quote_de,
                        verified=True,
                        evidence_de=verdict.evidence_de,
                        confidence=verdict.confidence,
                    )
                )
            else:
                self._audit.emit(
                    run_id,
                    "fact_dropped",
                    {
                        "claim": item.claim_de,
                        "confidence": verdict.confidence,
                        "present": verdict.present,
                    },
                )
        return facts

    def _source_context(self, sources: list[Source]) -> str:
        if not sources:
            return ""
        budget = max(
            self._settings.fetch_min_chars, self._settings.research_prompt_max_chars // len(sources)
        )
        blocks = []
        for source in sources:
            blocks.append(
                f"URL: {source.url}\nTITEL: {source.title}\nTEXT:\n{source.content[:budget]}"
            )
        return "\n\n---\n\n".join(blocks)

    @staticmethod
    def _hash(topic: Topic, sources: list[Source], facts: list[Fact]) -> str:
        payload = json.dumps(
            {
                "topic": topic.name_de,
                "urls": sorted(source.url for source in sources),
                "facts": sorted(fact.claim_de for fact in facts),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()
