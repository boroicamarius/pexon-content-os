"""The flexibility contract: provider names map to factories in one place."""

from __future__ import annotations

import importlib
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pexon.config.settings import Settings
from pexon.ports.errors import AdapterUnavailable

PortFactory = Callable[[Settings], Any]


@dataclass(frozen=True)
class AdapterSpec:
    """One registered adapter and its optional-dependency status."""

    module: str
    class_name: str
    available: bool
    reason: str

    @property
    def factory(self) -> PortFactory:
        """Import the adapter class only when selected."""
        module = importlib.import_module(self.module)
        return getattr(module, self.class_name)


def _spec(module: str, class_name: str) -> AdapterSpec:
    try:
        imported = importlib.import_module(module)
        available = bool(getattr(imported, "AVAILABLE", True))
        reason = str(getattr(imported, "UNAVAILABLE_REASON", ""))
    except Exception as exc:  # optional dependency missing at import time
        return AdapterSpec(module, class_name, False, f"import failed: {exc}")
    return AdapterSpec(module, class_name, available, reason)


# Adding a provider is one import-like spec line plus one dict entry in this file.
_LLM: dict[str, AdapterSpec] = {
    "openai-compatible": _spec("pexon.adapters.llm_openai_compatible", "OpenAICompatibleLLM"),
    "anthropic": _spec("pexon.adapters.llm_anthropic", "AnthropicLLM"),
    "gemini": _spec("pexon.adapters.llm_gemini", "GeminiLLM"),
}

_SEARCH: dict[str, AdapterSpec] = {
    "duckduckgo": _spec("pexon.adapters.search_duckduckgo", "DuckDuckGoSearch"),
    "tavily": _spec("pexon.adapters.search_tavily", "TavilySearch"),
    "brave": _spec("pexon.adapters.search_brave", "BraveSearch"),
    "serpapi": _spec("pexon.adapters.search_serpapi", "SerpAPISearch"),
}

_FETCH: dict[str, AdapterSpec] = {
    "trafilatura": _spec("pexon.adapters.fetch_trafilatura", "TrafilaturaFetcher"),
    "httpx": _spec("pexon.adapters.fetch_httpx", "HttpxFetcher"),
    "playwright": _spec("pexon.adapters.fetch_playwright", "PlaywrightFetcher"),
}

_EMBEDDINGS: dict[str, AdapterSpec] = {
    "openai-compatible": _spec(
        "pexon.adapters.embeddings_openai_compatible", "OpenAICompatibleEmbeddings"
    ),
    "local": _spec("pexon.adapters.embeddings_local", "LocalEmbeddings"),
}

_ANALYTICS: dict[str, AdapterSpec] = {
    "csv": _spec("pexon.adapters.analytics_csv", "CsvAnalytics"),
    "gsc": _spec("pexon.adapters.analytics_gsc", "GscAnalytics"),
    "plausible": _spec("pexon.adapters.analytics_plausible", "PlausibleAnalytics"),
    "matomo": _spec("pexon.adapters.analytics_matomo", "MatomoAnalytics"),
}

_CRM: dict[str, AdapterSpec] = {
    "csv": _spec("pexon.adapters.crm_csv", "CsvCrm"),
    "hubspot": _spec("pexon.adapters.crm_hubspot", "HubSpotCrm"),
}

_GEO: dict[str, AdapterSpec] = {
    "none": _spec("pexon.adapters.geo_none", "NoGeo"),
    "perplexity": _spec("pexon.adapters.geo_perplexity", "PerplexityGeo"),
    "openai": _spec("pexon.adapters.geo_openai", "OpenAIGeo"),
    "gemini": _spec("pexon.adapters.geo_gemini", "GeminiGeo"),
}

_KEYWORDS: dict[str, AdapterSpec] = {
    "csv": _spec("pexon.adapters.keywords_csv", "CsvKeywordDemand"),
    "dataforseo": _spec("pexon.adapters.keywords_dataforseo", "DataForSeoKeywords"),
}

_PUBLISHING: dict[str, AdapterSpec] = {
    "markdown": _spec("pexon.adapters.publishing_markdown", "MarkdownPublisher"),
    "wordpress": _spec("pexon.adapters.publishing_wordpress", "WordPressPublisher"),
    "webhook": _spec("pexon.adapters.publishing_webhook", "WebhookPublisher"),
}

_STORAGE: dict[str, AdapterSpec] = {
    "sqlite": _spec("pexon.adapters.storage_sqlite", "SqliteStorage"),
    "postgres": _spec("pexon.adapters.storage_postgres", "PostgresStorage"),
}

_CACHE: dict[str, AdapterSpec] = {
    "json": _spec("pexon.adapters.cache_json", "JsonCache"),
    "redis": _spec("pexon.adapters.cache_redis", "RedisCache"),
}

_TRACING: dict[str, AdapterSpec] = {
    "none": _spec("pexon.adapters.tracing_noop", "NoOpTracing"),
    "langsmith": _spec("pexon.adapters.tracing_langsmith", "LangSmithTracing"),
}

REGISTRY: dict[str, dict[str, AdapterSpec]] = {
    "llm": _LLM,
    "search": _SEARCH,
    "fetch": _FETCH,
    "embeddings": _EMBEDDINGS,
    "analytics": _ANALYTICS,
    "crm": _CRM,
    "geo": _GEO,
    "keywords": _KEYWORDS,
    "publishing": _PUBLISHING,
    "storage": _STORAGE,
    "cache": _CACHE,
    "tracing": _TRACING,
}


def build(port_name: str, provider_name: str, settings: Settings) -> Any:
    """Build the selected adapter, failing loudly when unavailable."""
    port = REGISTRY.get(port_name)
    if port is None:
        raise ValueError(f"unknown port: {port_name}")
    spec = port.get(provider_name)
    if spec is None:
        raise ValueError(f"unknown {port_name} provider: {provider_name}")
    if not spec.available:
        raise AdapterUnavailable(f"{port_name}/{provider_name}: {spec.reason}")
    return spec.factory(settings)


def providers(port_name: str) -> dict[str, AdapterSpec]:
    """List every registered adapter for a port."""
    return dict(REGISTRY.get(port_name, {}))


def active_provider(port_name: str, settings: Settings) -> str:
    """Resolve the active provider name for a port."""
    mapping = {
        "llm": settings.llm_provider_name,
        "search": settings.search_provider,
        "fetch": settings.fetch_provider,
        "embeddings": settings.embeddings_provider,
        "analytics": settings.analytics_provider,
        "crm": settings.crm_provider,
        "geo": settings.geo_provider,
        "keywords": settings.keyword_provider,
        "publishing": settings.publishing_provider,
        "storage": settings.storage_provider,
        "cache": settings.cache_provider,
        "tracing": settings.effective_tracing_provider,
    }
    return mapping[port_name]
