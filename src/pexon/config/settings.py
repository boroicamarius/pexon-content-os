"""Typed configuration; every tunable number is env-overridable."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from pydantic import PrivateAttr, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    """All runtime configuration, loaded from environment and .env files."""

    model_config = SettingsConfigDict(
        env_file=(str(_PROJECT_ROOT / ".env"),),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    _cli_overrides: set[str] = PrivateAttr(default_factory=set)

    # -- core -----------------------------------------------------------------
    app_env: str = "development"
    app_name: str = "pexon"
    log_level: str = "INFO"
    log_format: str = "json"
    timezone: str = "Europe/Berlin"
    site_base_url: str = "https://pexon.example"
    random_seed: int = 42

    # -- paths ----------------------------------------------------------------
    db_path: str = "db/pexon.db"
    schema_path: str = "db/schema.sql"
    analytics_csv: str = "data/analytics.csv"
    leads_csv: str = "data/leads.csv"
    keyword_csv: str = "data/keyword_demand.csv"
    content_dir: str = "content/posts"
    pending_dir: str = "content/pending"
    sitemap_path: str = "content/sitemap.xml"
    robots_path: str = "content/robots.txt"
    cache_dir: str = ".cache"

    # -- LLM generator --------------------------------------------------------
    llm_provider: str = "openai-compatible"
    llm_base_url: str = ""
    llm_api_key: SecretStr | None = None
    llm_model: str = ""
    llm_temperature: float = 0.4
    llm_max_tokens: int = 4096
    llm_timeout_seconds: float = 120.0
    llm_json_retries: int = 1

    # -- LLM judge (independent role) ----------------------------------------
    judge_llm_provider: str = ""
    judge_llm_base_url: str = ""
    judge_llm_api_key: SecretStr | None = None
    judge_llm_model: str = ""
    judge_llm_temperature: float = 0.0
    judge_llm_max_tokens: int = 1400

    # -- search ---------------------------------------------------------------
    search_provider: str = "duckduckgo"
    search_fallback_chain: str = "duckduckgo"
    search_results_per_query: int = 8
    search_timeout_seconds: float = 30.0
    serpapi_api_key: SecretStr | None = None
    tavily_api_key: SecretStr | None = None
    brave_api_key: SecretStr | None = None
    deep_research_user_agent: str = "Mozilla/5.0 (compatible; PexonResearch/0.1)"

    # -- fetch ----------------------------------------------------------------
    fetch_provider: str = "trafilatura"
    fetch_timeout_seconds: float = 30.0
    fetch_max_chars: int = 18000
    fetch_min_chars: int = 300
    fetch_top_n: int = 8
    fetch_workers: int = 6
    fetch_user_agent: str = "Mozilla/5.0 (compatible; PexonResearch/0.1)"
    playwright_headless: bool = True

    # -- embeddings -----------------------------------------------------------
    embeddings_provider: str = "openai-compatible"
    embeddings_base_url: str = ""
    embeddings_api_key: SecretStr | None = None
    embeddings_model: str = "nomic-embed-text"
    embeddings_timeout_seconds: float = 60.0
    embeddings_local_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    embeddings_local_dim: int = 512

    # -- analytics ------------------------------------------------------------
    analytics_provider: str = "csv"
    analytics_window_days: int = 28
    gsc_site_url: str = ""
    gsc_access_token: SecretStr | None = None
    gsc_refresh_token: SecretStr | None = None
    gsc_client_id: str = ""
    gsc_client_secret: SecretStr | None = None
    gsc_service_account_json: str = ""
    plausible_base_url: str = "https://plausible.io"
    plausible_site_id: str = ""
    plausible_api_key: SecretStr | None = None
    matomo_base_url: str = ""
    matomo_site_id: str = ""
    matomo_token: SecretStr | None = None

    # -- CRM / business outcomes ---------------------------------------------
    crm_provider: str = "csv"  # csv | hubspot
    crm_timeout_seconds: float = 30.0
    hubspot_api_key: SecretStr | None = None
    hubspot_article_property: str = "pexon_article_id"
    hubspot_pipeline_property: str = "pexon_pipeline_value"
    hubspot_won_property: str = "pexon_won_value"

    # -- GEO visibility (real AI answer engines) ------------------------------
    geo_provider: str = "none"  # none | perplexity | openai | gemini
    geo_brand_name: str = "Pexon"
    geo_domain: str = ""
    geo_query_count: int = 3
    geo_timeout_seconds: float = 60.0
    geo_perplexity_model: str = "sonar"
    geo_openai_model: str = "gpt-4.1-mini"
    geo_gemini_model: str = "gemini-2.5-flash"
    perplexity_api_key: SecretStr | None = None
    geo_openai_api_key: SecretStr | None = None
    geo_gemini_api_key: SecretStr | None = None

    # -- keyword demand / portfolio planning ----------------------------------
    keyword_provider: str = "csv"  # csv | dataforseo
    dataforseo_login: str = ""
    dataforseo_password: SecretStr | None = None
    keyword_location_code: int = 276  # Germany
    keyword_language_code: str = "de"
    keyword_timeout_seconds: float = 30.0
    plan_top_n: int = 10
    plan_min_volume: int = 0
    plan_ctr: float = 0.03
    plan_intent_weights: str = "informational=0.4,commercial=0.8,transactional=1.0,navigational=0.2"
    plan_funnel_weights: str = "top=0.5,middle=0.8,bottom=1.0"
    plan_difficulty_scale: float = 100.0
    plan_coverage_penalty: float = 0.50
    plan_volume_ceiling: int = 10000
    plan_candidate_pool: int = 50

    # -- publishing / technical SEO ------------------------------------------
    publishing_provider: str = "markdown"  # markdown | wordpress | webhook
    publishing_timeout_seconds: float = 30.0
    wordpress_base_url: str = ""
    wordpress_user: str = ""
    wordpress_app_password: SecretStr | None = None
    wordpress_status: str = "publish"
    webhook_url: str = ""
    webhook_token: SecretStr | None = None
    internal_link_count: int = 2
    internal_link_lookback: int = 25
    meta_description_chars: int = 155
    sitemap_enabled: bool = True

    # -- human review ---------------------------------------------------------
    require_human_review: bool = False

    # -- economics ------------------------------------------------------------
    llm_input_cost_per_1k: float = 0.0
    llm_output_cost_per_1k: float = 0.0
    search_cost_per_call: float = 0.0
    fetch_cost_per_call: float = 0.0
    article_fixed_cost: float = 0.0
    cost_currency: str = "USD"

    # -- funnel ---------------------------------------------------------------
    funnel_window_days: int = 90

    # -- storage / cache / tracing -------------------------------------------
    storage_provider: str = "sqlite"
    database_url: str = ""
    cache_provider: str = "json"
    cache_ttl_seconds: int = 86400
    redis_url: str = ""
    tracing_provider: str = "none"
    langchain_tracing_v2: bool = False
    langsmith_project: str = "pexon"

    # -- research thresholds --------------------------------------------------
    research_query_count: int = 4
    fact_verification_max_chars: int = 7000
    research_prompt_max_chars: int = 30000
    research_max_facts: int = 20
    fact_confidence_min: float = 0.55
    research_workers: int = 4
    citation_verify_threshold: float = 0.58

    # -- generation thresholds ------------------------------------------------
    gen_sample_count: int = 3
    gen_refine_top_k: int = 1
    gen_angles: str = "direkt,deep,compliance,management,praxis"
    direction_key_points: int = 5
    judge_body_max_chars: int = 16000
    max_retries: int = 2
    draft_max_tokens: int = 4200
    baseline_clicks: float = 40.0
    baseline_impressions: float = 1200.0
    dup_sim_threshold: float = 0.92
    semantic_dedupe_threshold: float = 0.88
    judge_factuality_min: float = 0.75
    judge_compliance_min: float = 0.80
    judge_fluency_min: float = 0.80
    compliance_min_matches: int = 2
    min_citations: int = 2
    min_article_words: int = 350
    answer_first_max_words: int = 70
    entity_target_count: int = 8
    heading_target_count: int = 6
    freshness_reference_days: int = 365
    feature_freshness_missing: float = 0.50
    slug_max_length: int = 90
    expected_default_position: float = 10.0
    feature_answer_first_fallback: float = 0.30
    feature_seo_keyword_weight: float = 0.50
    feature_seo_structure_weight: float = 0.50
    feature_geo_entity_weight: float = 0.45
    feature_geo_structure_weight: float = 0.35
    feature_geo_heading_weight: float = 0.20
    feature_aeo_answer_weight: float = 0.60
    feature_aeo_entity_weight: float = 0.25
    feature_aeo_faq_bonus: float = 0.15
    duplicate_corpus_limit: int = 50
    citation_target_count: int = 6
    draft_target_words: int = 900
    draft_max_words: int = 1600
    german_min_score: float = 0.42
    german_stopword_multiplier: float = 2.2
    german_umlaut_bonus_cap: float = 0.15
    german_sample_chars: int = 6000

    # -- intelligence thresholds ---------------------------------------------
    competitor_top_n: int = 6
    competitor_search_queries: int = 2
    intelligence_engines: str = "chatgpt,perplexity,gemini,claude"
    engine_answer_max_tokens: int = 900
    engine_answer_excerpt_chars: int = 3500
    page_rank_max_tokens: int = 1200
    insight_max_tokens: int = 1200
    intelligence_workers: int = 4

    # -- learner thresholds ---------------------------------------------------
    min_training_rows: int = 12
    train_test_split: float = 0.25
    champion_min_delta: float = 0.0
    bootstrap_iterations: int = 400
    ci_lower_percentile: float = 0.10
    ci_upper_percentile: float = 0.90
    gb_n_estimators: int = 120
    gb_learning_rate: float = 0.05
    gb_max_depth: int = 3
    gb_min_samples_leaf: int = 5
    gb_subsample: float = 0.9
    cold_start_click_multiplier: float = 1.35
    cold_start_impression_multiplier: float = 1.35
    cold_start_ci_spread: float = 0.28
    citation_coverage_min: float = 0.5

    # -- drift thresholds -----------------------------------------------------
    drift_psi_threshold: float = 0.20
    drift_ks_threshold: float = 0.20
    drift_window_days: int = 28
    drift_min_rows: int = 8
    drift_bins: int = 10
    drift_epsilon: float = 0.000001

    # -- reflection thresholds ------------------------------------------------
    max_iterations: int = 2
    propose_error_threshold: float = 0.35
    reflection_prompt_max_tokens: int = 1400

    # -- guards ---------------------------------------------------------------
    compliance_keywords: str = "DSGVO,DORA,MaRisk,AI Act"
    injection_patterns: str = (
        r"ignore (all |any )?(previous|prior) instructions,"
        r"disregard (all |any )?(previous|prior) instructions,"
        r"system prompt,"
        r"you are now,"
        r"reveal (your|the) (system )?prompt,"
        r"developer mode,"
        r"jailbreak"
    )
    pii_public_figures: str = ""
    pii_redaction_token: str = "[REDACTED]"

    # -- runtime --------------------------------------------------------------
    drill_fetch_url: str = "https://example.com"
    recursion_limit: int = 120
    stream_mode: str = "updates"

    @field_validator(
        "llm_provider",
        "judge_llm_provider",
        "search_provider",
        "fetch_provider",
        "embeddings_provider",
        "analytics_provider",
        "storage_provider",
        "cache_provider",
        "tracing_provider",
        "crm_provider",
        "geo_provider",
        "keyword_provider",
        "publishing_provider",
        mode="before",
    )
    @classmethod
    def _provider_lower(cls, value: object) -> str:
        return str(value or "").strip().lower()

    @field_validator("train_test_split", "gb_subsample")
    @classmethod
    def _unit_interval(cls, value: float) -> float:
        if not 0.0 < value < 1.0:
            raise ValueError("must be between 0 and 1")
        return value

    @property
    def project_root(self) -> Path:
        """Absolute project root."""
        return _PROJECT_ROOT

    def resolve_path(self, value: str | Path) -> Path:
        """Resolve a configured path against the project root."""
        path = Path(value)
        return path if path.is_absolute() else _PROJECT_ROOT / path

    @property
    def sqlite_path(self) -> Path:
        """SQLite database path."""
        return self.resolve_path(self.db_path)

    @property
    def schema_file(self) -> Path:
        """Schema SQL path."""
        return self.resolve_path(self.schema_path)

    @property
    def analytics_file(self) -> Path:
        """CSV analytics path."""
        return self.resolve_path(self.analytics_csv)

    @property
    def content_path(self) -> Path:
        """Blog output directory."""
        return self.resolve_path(self.content_dir)

    @property
    def pending_path(self) -> Path:
        """Human-review staging directory."""
        return self.resolve_path(self.pending_dir)

    @property
    def leads_path(self) -> Path:
        """CSV CRM export path."""
        return self.resolve_path(self.leads_csv)

    @property
    def keyword_path(self) -> Path:
        """CSV keyword-demand path."""
        return self.resolve_path(self.keyword_csv)

    @property
    def sitemap_file(self) -> Path:
        """Generated sitemap path."""
        return self.resolve_path(self.sitemap_path)

    @property
    def robots_file(self) -> Path:
        """Generated robots.txt path."""
        return self.resolve_path(self.robots_path)

    @property
    def cache_path(self) -> Path:
        """Filesystem cache directory."""
        return self.resolve_path(self.cache_dir)

    @property
    def llm_provider_name(self) -> str:
        """Generator provider name."""
        return self.llm_provider.strip().lower()

    @property
    def judge_provider_name(self) -> str:
        """Judge provider, defaulting to the generator."""
        return (self.judge_llm_provider or self.llm_provider).strip().lower()

    @property
    def effective_llm_base_url(self) -> str:
        """Provider-appropriate generator base URL."""
        return self.llm_base_url.strip() or self._default_base_url(self.llm_provider_name)

    @property
    def effective_llm_model(self) -> str:
        """Generator model, defaulted per provider."""
        return self.llm_model.strip() or self._default_model(self.llm_provider_name)

    @property
    def effective_llm_api_key(self) -> str:
        """Generator key, with a zero-key local default."""
        if self.llm_api_key is not None and self.llm_api_key.get_secret_value():
            return self.llm_api_key.get_secret_value()
        return "not-needed" if self.llm_provider_name == "openai-compatible" else ""

    @property
    def effective_judge_base_url(self) -> str:
        """Provider-appropriate judge base URL."""
        if self.judge_llm_base_url.strip():
            return self.judge_llm_base_url.strip()
        if self.judge_provider_name == self.llm_provider_name:
            return self.effective_llm_base_url
        return self._default_base_url(self.judge_provider_name)

    @property
    def effective_judge_model(self) -> str:
        """Judge model, defaulted independently."""
        if self.judge_llm_model.strip():
            return self.judge_llm_model.strip()
        if self.judge_provider_name == self.llm_provider_name:
            return self.effective_llm_model
        return self._default_model(self.judge_provider_name)

    @property
    def effective_judge_api_key(self) -> str:
        """Judge key, falling back to the generator key only for the same provider."""
        if self.judge_llm_api_key is not None and self.judge_llm_api_key.get_secret_value():
            return self.judge_llm_api_key.get_secret_value()
        if self.judge_provider_name == self.llm_provider_name:
            return self.effective_llm_api_key
        return ""

    def judge_settings(self) -> Settings:
        """Return a Settings view whose llm_* fields describe the judge role."""
        clone = self.model_copy(
            update={
                "llm_provider": self.judge_provider_name,
                "llm_base_url": self.effective_judge_base_url,
                "llm_api_key": SecretStr(self.effective_judge_api_key)
                if self.effective_judge_api_key
                else None,
                "llm_model": self.effective_judge_model,
                "llm_temperature": self.judge_llm_temperature,
                "llm_max_tokens": self.judge_llm_max_tokens,
            }
        )
        clone._cli_overrides = set(self._cli_overrides)
        return clone

    @property
    def effective_embeddings_base_url(self) -> str:
        """Embedding endpoint, reusing the generator endpoint for local OpenAI-compatible stacks."""
        if self.embeddings_base_url.strip():
            return self.embeddings_base_url.strip()
        if self.llm_provider_name == "openai-compatible":
            return self.effective_llm_base_url
        return "https://api.openai.com/v1"

    @property
    def effective_embeddings_api_key(self) -> str:
        """Embedding key, falling back to the LLM key only for a shared endpoint."""
        if self.embeddings_api_key is not None and self.embeddings_api_key.get_secret_value():
            return self.embeddings_api_key.get_secret_value()
        if self.effective_embeddings_base_url == self.effective_llm_base_url:
            return self.effective_llm_api_key
        return "not-needed"

    @property
    def effective_geo_domain(self) -> str:
        """GEO domain, falling back to the public site host."""
        return self.geo_domain or urlparse(self.site_base_url).netloc

    @property
    def geo_enabled(self) -> bool:
        """Whether real AI-engine visibility measurement is configured."""
        return self.geo_provider != "none"

    @property
    def plan_intent_map(self) -> dict[str, float]:
        """Parse intent-name to weight mappings."""
        return self._parse_weight_map(self.plan_intent_weights)

    @property
    def plan_funnel_map(self) -> dict[str, float]:
        """Parse funnel-stage to weight mappings."""
        return self._parse_weight_map(self.plan_funnel_weights)

    @property
    def judge_is_separate(self) -> bool:
        """Whether the judge is a genuinely different provider/model."""
        return (self.judge_provider_name, self.effective_judge_model) != (
            self.llm_provider_name,
            self.effective_llm_model,
        )

    @property
    def effective_tracing_provider(self) -> str:
        """LangSmith is opt-in through either explicit provider or LANGCHAIN_TRACING_V2."""
        if self.tracing_provider != "none":
            return self.tracing_provider
        return "langsmith" if self.langchain_tracing_v2 else "none"

    @property
    def fallback_providers(self) -> list[str]:
        """Ordered search fallback chain, starting with the active provider."""
        chain = [p.strip().lower() for p in self.search_fallback_chain.split(",") if p.strip()]
        active = self.search_provider.strip().lower()
        return list(dict.fromkeys([active, *chain])) if chain else [active]

    @property
    def compliance_terms(self) -> list[str]:
        """Configured German compliance keywords."""
        return [t.strip() for t in self.compliance_keywords.split(",") if t.strip()]

    @property
    def engines(self) -> list[str]:
        """Configured generative-engine personas."""
        return [e.strip().lower() for e in self.intelligence_engines.split(",") if e.strip()]

    @property
    def public_figures(self) -> list[str]:
        """Configured public-figure names for PII redaction."""
        return [n.strip() for n in self.pii_public_figures.split(",") if n.strip()]

    @property
    def injection_pattern_list(self) -> list[str]:
        """Configured prompt-injection regexes."""
        return [p.strip() for p in self.injection_patterns.split(",") if p.strip()]

    @property
    def provider_config(self) -> dict[str, object]:
        """Safe provider provenance for events and model cards."""
        return {
            "llm": {
                "provider": self.llm_provider_name,
                "model": self.effective_llm_model,
                "base_url": self.effective_llm_base_url,
            },
            "judge": {
                "provider": self.judge_provider_name,
                "model": self.effective_judge_model,
                "base_url": self.effective_judge_base_url,
                "separate": self.judge_is_separate,
            },
            "search": {"provider": self.search_provider, "fallback": self.fallback_providers},
            "fetch": {"provider": self.fetch_provider},
            "embeddings": {
                "provider": self.embeddings_provider,
                "model": self.embeddings_model,
            },
            "analytics": {"provider": self.analytics_provider},
            "crm": {"provider": self.crm_provider},
            "geo": {
                "provider": self.geo_provider,
                "brand": self.geo_brand_name,
                "domain": self.effective_geo_domain,
            },
            "keywords": {"provider": self.keyword_provider},
            "publishing": {"provider": self.publishing_provider},
            "storage": {"provider": self.storage_provider},
            "cache": {"provider": self.cache_provider},
            "tracing": {"provider": self.effective_tracing_provider},
        }

    def with_cli_overrides(self, **updates: Any) -> Settings:
        """Apply CLI overrides and remember their provenance."""
        clean = {k: v for k, v in updates.items() if v is not None}
        clone = self.model_copy(update=clean)
        clone._cli_overrides = set(self._cli_overrides) | set(clean)
        if "llm_base_url" in clean or "llm_model" in clean:
            clone._cli_overrides.add("llm_provider")
        return clone

    def source_for(self, field_name: str) -> str:
        """Return cli, env or default for one field."""
        if field_name in self._cli_overrides:
            return "cli"
        if field_name in self.model_fields_set or f"{field_name.upper()}" in os.environ:
            return "env"
        return "default"

    @staticmethod
    def _parse_weight_map(raw: str) -> dict[str, float]:
        result: dict[str, float] = {}
        for item in raw.split(","):
            if "=" in item:
                key, value = item.split("=", 1)
                try:
                    result[key.strip().lower()] = float(value)
                except ValueError:
                    continue
        return result

    @staticmethod
    def _default_base_url(provider: str) -> str:
        return {
            "openai-compatible": "http://localhost:11434/v1",
            "anthropic": "https://api.anthropic.com",
            "gemini": "https://generativelanguage.googleapis.com",
        }.get(provider, "http://localhost:11434/v1")

    @staticmethod
    def _default_model(provider: str) -> str:
        return {
            "openai-compatible": "llama3.1",
            "anthropic": "claude-sonnet-4-5",
            "gemini": "gemini-2.5-flash",
        }.get(provider, "llama3.1")

    def ensure_directories(self) -> None:
        """Create writable runtime directories."""
        for path in (
            self.sqlite_path.parent,
            self.analytics_file.parent,
            self.content_path,
            self.pending_path,
            self.sitemap_file.parent,
            self.leads_path.parent,
            self.keyword_path.parent,
            self.cache_path,
        ):
            path.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process settings singleton."""
    settings = Settings()
    settings.ensure_directories()
    return settings
