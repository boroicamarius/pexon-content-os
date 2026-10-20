# Changelog

All notable changes to this prototype are recorded here.

## [0.2.0] — 2026-10-21

### Repository identity

- Public repository renamed to **`pexon-content-os`** (product remains Pexon).

### Added — measurement layer

- `CrmPort` with CSV and HubSpot adapters.
- Lead, funnel, attribution and economics models.
- `AttributionService` joining analytics, CRM and article costs.
- Real GEO measurement with `GeoPort` adapters for Perplexity, OpenAI web search and
  Gemini grounding; explicit `none` default.
- `GeoService` and persisted `geo_visibility` observations.
- Demand-aware portfolio planning with CSV and DataForSEO keyword adapters.
- `pexon plan`, `pexon report`, `pexon geo`, `pexon approve`, `pexon measure`,
  `pexon seed-leads` and `pexon seed-keywords`.
- Technical SEO service: canonical, meta description, JSON-LD, internal links,
  sitemap and robots.
- `PublishingPort` with Markdown, WordPress and webhook adapters.
- Optional human review with `content/pending/` staging and `reviews`.
- Per-article cost accounting (`article_costs`).
- Final `report` node in the top-level LangGraph.
- CEO brief, architecture diagrams, provider matrix, KPI model, operations and
  security documentation.

### Changed

- Top-level graph routes `pending_review` to end.
- Article model carries target keyword, cluster, funnel stage, canonical URL,
  external publishing metadata and review state.
- `pexon doctor` probes CRM, GEO, keyword and publishing adapters.
- README is now a CEO-facing repository landing page.

### Fixed

- Per-sample generation failure is logged and does not abort the other samples.
- Metrics snapshot aggregation is defensive against labelled counters.
- Review approval performs a full-row update and rewrites frontmatter.
- Duplicate gate fails closed when embeddings are unavailable.

## [0.1.0] — 2026-10-20

### Added

- Four LangGraph subgraphs: Research, Generation, Intelligence, Reflection.
- Services for each frame.
- Ports/adapters registry with zero-key defaults.
- LLM, search, fetch, embeddings, analytics, storage, cache and tracing adapters.
- Verified research ground truth.
- `Send` fan-out generation.
- Calibrated predictor, champion–challenger learner, isotonic calibration and drift.
- Two-pass quality gate.
- SQLite checkpointer and replay.
- CLI, inspection commands and audit events.
