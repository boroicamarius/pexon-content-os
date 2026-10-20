"""Composition root; the only place that knows about the registry and services."""

from __future__ import annotations

from dataclasses import dataclass

from pexon.adapters import registry
from pexon.config.settings import Settings, get_settings
from pexon.graph.pexon_graph import PexonGraph
from pexon.observability.metrics import MetricsCollector
from pexon.ports.analytics import AnalyticsPort
from pexon.ports.cache import CachePort
from pexon.ports.crm import CrmPort
from pexon.ports.embeddings import EmbeddingsPort
from pexon.ports.fetch import FetchPort
from pexon.ports.geo import GeoPort
from pexon.ports.keywords import KeywordPort
from pexon.ports.llm import LLMPort
from pexon.ports.publishing import PublishingPort
from pexon.ports.search import SearchPort
from pexon.ports.storage import StoragePort
from pexon.ports.tracing import TracingPort
from pexon.services.attribution import AttributionService
from pexon.services.audit import AuditLog
from pexon.services.drift import DriftMonitor
from pexon.services.economics import EconomicsService
from pexon.services.features import FeatureExtractor
from pexon.services.gateway import LLMGateway
from pexon.services.generation_service import GenerationService
from pexon.services.geo import GeoService
from pexon.services.intelligence_service import IntelligenceService
from pexon.services.learner import Learner
from pexon.services.portfolio import PortfolioService
from pexon.services.predictor import Predictor
from pexon.services.reflection_service import ReflectionService
from pexon.services.research_service import ResearchService
from pexon.services.seo import SeoService


@dataclass
class Runtime:
    """Fully wired application graph and its ports."""

    settings: Settings
    metrics: MetricsCollector
    storage: StoragePort
    cache: CachePort
    search: SearchPort
    fetch: FetchPort
    llm: LLMPort
    judge_llm: LLMPort
    embeddings: EmbeddingsPort
    analytics: AnalyticsPort
    crm: CrmPort
    geo: GeoPort
    keywords: KeywordPort
    publishing: PublishingPort
    tracing: TracingPort
    economics: EconomicsService
    attribution: AttributionService
    geo_service: GeoService
    portfolio: PortfolioService
    reflection: ReflectionService
    audit: AuditLog
    graph: PexonGraph


def build_runtime(settings: Settings | None = None) -> Runtime:
    """Build every active adapter and the four services exactly once."""
    settings = settings or get_settings()
    settings.ensure_directories()
    metrics = MetricsCollector()
    storage: StoragePort = registry.build("storage", settings.storage_provider, settings)
    storage.setup()
    cache: CachePort = registry.build("cache", settings.cache_provider, settings)
    search: SearchPort = registry.build("search", settings.search_provider, settings)
    fetch: FetchPort = registry.build("fetch", settings.fetch_provider, settings)
    llm: LLMPort = registry.build("llm", settings.llm_provider_name, settings)
    judge_settings = settings.judge_settings()
    judge_llm: LLMPort = registry.build("llm", settings.judge_provider_name, judge_settings)
    embeddings: EmbeddingsPort = registry.build(
        "embeddings", settings.embeddings_provider, settings
    )
    analytics: AnalyticsPort = registry.build("analytics", settings.analytics_provider, settings)
    crm: CrmPort = registry.build("crm", settings.crm_provider, settings)
    geo: GeoPort = registry.build("geo", settings.geo_provider, settings)
    keywords: KeywordPort = registry.build("keywords", settings.keyword_provider, settings)
    publishing: PublishingPort = registry.build(
        "publishing", settings.publishing_provider, settings
    )
    tracing: TracingPort = registry.build("tracing", settings.effective_tracing_provider, settings)

    generator_gateway = LLMGateway(llm, settings, metrics)
    judge_gateway = LLMGateway(judge_llm, judge_settings, metrics)
    audit = AuditLog(storage)
    features = FeatureExtractor(settings)
    predictor = Predictor(settings, storage)
    learner = Learner(settings, storage, audit)
    drift = DriftMonitor(settings, storage, audit)
    economics = EconomicsService(settings, metrics, storage)
    seo = SeoService(settings, storage)
    attribution = AttributionService(settings, crm, storage, economics, audit)
    geo_service = GeoService(settings, geo, storage, audit)
    portfolio = PortfolioService(settings, keywords, storage, audit)

    def search_factory(provider: str) -> SearchPort:
        return registry.build("search", provider, settings)

    research = ResearchService(
        settings,
        search,
        fetch,
        generator_gateway,
        judge_gateway,
        cache,
        storage,
        audit,
        metrics,
        search_factory,
    )
    intelligence = IntelligenceService(
        settings,
        search,
        generator_gateway,
        embeddings,
        storage,
        learner,
        drift,
        audit,
        metrics,
        search_factory,
    )
    generation = GenerationService(
        settings,
        generator_gateway,
        judge_gateway,
        embeddings,
        predictor,
        features,
        storage,
        audit,
        metrics,
    )
    reflection = ReflectionService(
        settings,
        generator_gateway,
        analytics,
        storage,
        features,
        learner,
        audit,
        metrics,
        publishing,
        seo,
        economics,
    )
    graph = PexonGraph(
        settings,
        research,
        intelligence,
        generation,
        reflection,
        audit,
        metrics,
        tracing,
        geo_service,
        attribution,
    )
    return Runtime(
        settings=settings,
        metrics=metrics,
        storage=storage,
        cache=cache,
        search=search,
        fetch=fetch,
        llm=llm,
        judge_llm=judge_llm,
        embeddings=embeddings,
        analytics=analytics,
        crm=crm,
        geo=geo,
        keywords=keywords,
        publishing=publishing,
        tracing=tracing,
        economics=economics,
        attribution=attribution,
        geo_service=geo_service,
        portfolio=portfolio,
        reflection=reflection,
        audit=audit,
        graph=graph,
    )
