-- Pexon prototype schema. Applied idempotently on first run.
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS topics (
    id TEXT PRIMARY KEY,
    name_de TEXT NOT NULL,
    bank_segment TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS research_snapshots (
    id TEXT PRIMARY KEY,
    topic_id TEXT NOT NULL,
    snapshot_hash TEXT NOT NULL,
    facts_json TEXT NOT NULL,
    sources_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS articles (
    id TEXT PRIMARY KEY,
    topic_id TEXT NOT NULL,
    title_de TEXT NOT NULL,
    body_md TEXT NOT NULL,
    status TEXT NOT NULL,
    prompt_version TEXT NOT NULL,
    model_version TEXT NOT NULL,
    slug TEXT,
    target_keyword TEXT,
    cluster TEXT,
    funnel_stage TEXT,
    canonical_url TEXT,
    external_url TEXT,
    external_id TEXT,
    staged_path TEXT,
    review_status TEXT NOT NULL DEFAULT 'published',
    reviewed_by TEXT,
    provider_config_json TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS drafts (
    id TEXT PRIMARY KEY,
    article_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    body_md TEXT NOT NULL,
    signals_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS predictions (
    id TEXT PRIMARY KEY,
    article_id TEXT NOT NULL,
    model_version TEXT NOT NULL,
    clicks REAL NOT NULL,
    impressions REAL NOT NULL,
    position REAL NOT NULL,
    ci_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS performance (
    id TEXT PRIMARY KEY,
    article_id TEXT NOT NULL,
    clicks REAL NOT NULL,
    impressions REAL NOT NULL,
    position REAL NOT NULL,
    measured_at TEXT NOT NULL,
    source TEXT,
    page_url TEXT
);

CREATE TABLE IF NOT EXISTS features (
    id TEXT PRIMARY KEY,
    article_id TEXT NOT NULL,
    features_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS weights (
    id TEXT PRIMARY KEY,
    version TEXT NOT NULL UNIQUE,
    values_json TEXT NOT NULL,
    intercept REAL NOT NULL,
    trained_at TEXT NOT NULL,
    model_json TEXT,
    calibration_json TEXT,
    backend TEXT NOT NULL DEFAULT 'pexon-gb',
    metrics_json TEXT,
    row_count INTEGER NOT NULL DEFAULT 0,
    provider_config_json TEXT
);

CREATE TABLE IF NOT EXISTS model_cards (
    id TEXT PRIMARY KEY,
    version TEXT NOT NULL,
    features_json TEXT NOT NULL,
    metrics_json TEXT NOT NULL,
    known_limits TEXT NOT NULL,
    row_count INTEGER NOT NULL,
    provider_config_json TEXT NOT NULL,
    trained_at TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS events (
    id TEXT PRIMARY KEY,
    ts TEXT NOT NULL,
    run_id TEXT NOT NULL,
    article_id TEXT,
    kind TEXT NOT NULL,
    payload_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS leads (
    id TEXT PRIMARY KEY,
    article_id TEXT,
    created_at TEXT NOT NULL,
    source TEXT,
    medium TEXT,
    campaign TEXT,
    page_url TEXT,
    status TEXT NOT NULL,
    company TEXT,
    annual_value REAL NOT NULL DEFAULT 0,
    currency TEXT NOT NULL DEFAULT 'EUR',
    client INTEGER NOT NULL DEFAULT 0,
    won_value REAL NOT NULL DEFAULT 0,
    crm_url TEXT,
    provider TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS geo_visibility (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    article_id TEXT,
    topic_id TEXT NOT NULL,
    engine TEXT NOT NULL,
    query TEXT NOT NULL,
    brand_mentioned INTEGER NOT NULL,
    domain_cited INTEGER NOT NULL,
    citations_json TEXT NOT NULL,
    answer_excerpt TEXT NOT NULL,
    measured_at TEXT NOT NULL,
    provider TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS article_costs (
    id TEXT PRIMARY KEY,
    article_id TEXT NOT NULL,
    run_id TEXT NOT NULL,
    llm_input_tokens INTEGER NOT NULL,
    llm_output_tokens INTEGER NOT NULL,
    search_calls INTEGER NOT NULL,
    fetch_calls INTEGER NOT NULL,
    llm_cost REAL NOT NULL,
    search_cost REAL NOT NULL,
    fetch_cost REAL NOT NULL,
    fixed_cost REAL NOT NULL,
    total_cost REAL NOT NULL,
    currency TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS reviews (
    id TEXT PRIMARY KEY,
    article_id TEXT NOT NULL,
    reviewer TEXT NOT NULL,
    decision TEXT NOT NULL,
    notes TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS funnel_reports (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    since TEXT NOT NULL,
    until TEXT NOT NULL,
    report_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS content_plans (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    plan_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS prompt_variants (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    version INTEGER NOT NULL,
    template_de TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_research_topic ON research_snapshots(topic_id);
CREATE INDEX IF NOT EXISTS idx_articles_topic ON articles(topic_id);
CREATE INDEX IF NOT EXISTS idx_articles_status ON articles(status);
CREATE INDEX IF NOT EXISTS idx_predictions_article ON predictions(article_id);
CREATE INDEX IF NOT EXISTS idx_performance_article ON performance(article_id);
CREATE INDEX IF NOT EXISTS idx_features_article ON features(article_id);
CREATE INDEX IF NOT EXISTS idx_events_run ON events(run_id);
CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts);
CREATE INDEX IF NOT EXISTS idx_prompt_variants_name ON prompt_variants(name, created_at);
CREATE INDEX IF NOT EXISTS idx_leads_article ON leads(article_id);
CREATE INDEX IF NOT EXISTS idx_leads_created ON leads(created_at);
CREATE INDEX IF NOT EXISTS idx_geo_article ON geo_visibility(article_id);
CREATE INDEX IF NOT EXISTS idx_geo_run ON geo_visibility(run_id);
CREATE INDEX IF NOT EXISTS idx_costs_article ON article_costs(article_id);
CREATE INDEX IF NOT EXISTS idx_reviews_article ON reviews(article_id);
CREATE INDEX IF NOT EXISTS idx_funnel_run ON funnel_reports(run_id);

INSERT INTO schema_version(version, applied_at)
SELECT 2, CURRENT_TIMESTAMP
WHERE NOT EXISTS (SELECT 1 FROM schema_version);
