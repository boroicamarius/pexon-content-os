# Provider matrix

Pexon has **12 ports** and **33 registered adapters**. The default stack is zero-key.
A bank deployment changes environment variables only; no service, graph or subgraph is
modified.

## 1. At a glance

| Port | Default | Adapters | Primary env |
|---|---|---|---|
| LLM | `openai-compatible` | openai-compatible, anthropic, gemini | `LLM_PROVIDER` |
| Judge LLM | same as LLM | any LLM adapter, independent config | `JUDGE_LLM_*` |
| Search | `duckduckgo` | duckduckgo, tavily, brave, serpapi | `SEARCH_PROVIDER` |
| Fetch | `trafilatura` | trafilatura, httpx, playwright | `FETCH_PROVIDER` |
| Embeddings | `openai-compatible` | openai-compatible, local | `EMBEDDINGS_PROVIDER` |
| Analytics | `csv` | csv, gsc, plausible, matomo | `ANALYTICS_PROVIDER` |
| CRM | `csv` | csv, hubspot | `CRM_PROVIDER` |
| GEO | `none` | none, perplexity, openai, gemini | `GEO_PROVIDER` |
| Keywords | `csv` | csv, dataforseo | `KEYWORD_PROVIDER` |
| Publishing | `markdown` | markdown, wordpress, webhook | `PUBLISHING_PROVIDER` |
| Storage | `sqlite` | sqlite, postgres | `STORAGE_PROVIDER` |
| Cache | `json` | json, redis | `CACHE_PROVIDER` |
| Tracing | `none` | none, langsmith | `TRACING_PROVIDER` |

## 2. Adapter details

### LLM

| Provider | Protocol / SDK | Required env | Notes |
|---|---|---|---|
| `openai-compatible` | OpenAI chat completions; `langchain-openai` when installed, otherwise OpenAI SDK | `LLM_BASE_URL`, `LLM_MODEL`, optionally `LLM_API_KEY` | Works with OpenAI, Azure OpenAI, Ollama, vLLM, LiteLLM, OpenRouter, Together, Groq, DeepSeek, Mistral API, Fireworks, Anyscale, xAI |
| `anthropic` | Native Anthropic SDK when installed, raw Messages API otherwise | `LLM_API_KEY`, optionally `LLM_BASE_URL`, `LLM_MODEL` | Default model `claude-sonnet-4-5` |
| `gemini` | google-genai when installed, raw REST otherwise | `LLM_API_KEY`, optionally `LLM_BASE_URL`, `LLM_MODEL` | Default model `gemini-2.5-flash` |

The judge has its own namespace: `JUDGE_LLM_PROVIDER`, `JUDGE_LLM_BASE_URL`,
`JUDGE_LLM_MODEL`, `JUDGE_LLM_API_KEY`, `JUDGE_LLM_TEMPERATURE`,
`JUDGE_LLM_MAX_TOKENS`. If the judge resolves to the same provider/model as the
generator, an audit event `judge_same_provider` is emitted and `doctor` warns.

### Search

| Provider | Required key | Notes |
|---|---|---|
| `duckduckgo` | none | Public HTML endpoint; parses result anchors |
| `tavily` | `TAVILY_API_KEY` | Tavily search API |
| `brave` | `BRAVE_API_KEY` | Brave Web Search API |
| `serpapi` | `SERPAPI_API_KEY` | Google SERP via SerpAPI |

`SEARCH_FALLBACK_CHAIN` is ordered. Every failed provider and every fallback emits an
event.

### Fetch

| Provider | Optional package | Notes |
|---|---|---|
| `trafilatura` | `trafilatura` | Main-content extraction, with stdlib fallback |
| `httpx` | none | Raw HTTP + stdlib HTML text |
| `playwright` | `playwright` | JavaScript rendering; marked unavailable without the package/browser |

### Embeddings

| Provider | Required env | Notes |
|---|---|---|
| `openai-compatible` | `EMBEDDINGS_BASE_URL`, `EMBEDDINGS_MODEL` | Ollama, OpenAI or any `/embeddings` endpoint |
| `local` | none | sentence-transformers when installed; deterministic hashed multilingual n-grams otherwise |

### Analytics

| Provider | Required env | Notes |
|---|---|---|
| `csv` | none | `data/analytics.csv` |
| `gsc` | `GSC_SITE_URL` + service account or refresh token | Search Console page-level query |
| `plausible` | `PLAUSIBLE_SITE_ID`, `PLAUSIBLE_API_KEY` | Visitors → clicks, pageviews → impressions |
| `matomo` | `MATOMO_BASE_URL`, `MATOMO_SITE_ID`, `MATOMO_TOKEN` | Visits → clicks, hits → impressions |

### CRM

| Provider | Required env | Notes |
|---|---|---|
| `csv` | none | `data/leads.csv`; privacy-preserving export |
| `hubspot` | `HUBSPOT_API_KEY` | CRM v3 contact search; article attribution via custom property |

HubSpot mapping:

- `HUBSPOT_ARTICLE_PROPERTY` → article ID;
- `HUBSPOT_PIPELINE_PROPERTY` → annual/pipeline value;
- `HUBSPOT_WON_PROPERTY` → won value.

The adapter does not request or store email addresses.

### GEO

| Provider | Required env | Notes |
|---|---|---|
| `none` | none | Explicit no-op; returns a disabled report |
| `perplexity` | `PERPLEXITY_API_KEY` | Sonar API; citation URLs |
| `openai` | `GEO_OPENAI_API_KEY` | Responses API + web search; URL annotations |
| `gemini` | `GEO_GEMINI_API_KEY` | Grounding with Google Search; grounding chunks |

GEO is deliberately **not** inferred from the generator provider. If no real engine is
configured, the metric remains unmeasured.

### Keywords

| Provider | Required env | Notes |
|---|---|---|
| `csv` | none | `data/keyword_demand.csv` |
| `dataforseo` | `DATAFORSEO_LOGIN`, `DATAFORSEO_PASSWORD` | Google Ads search volume via DataForSEO |

### Publishing

| Provider | Required env | Notes |
|---|---|---|
| `markdown` | none | Writes `content/posts/<slug>.md` |
| `wordpress` | `WORDPRESS_BASE_URL`, `WORDPRESS_USER`, `WORDPRESS_APP_PASSWORD` | Real REST API; application password |
| `webhook` | `WEBHOOK_URL`, optionally `WEBHOOK_TOKEN` | POSTs the complete article payload |

### Storage, cache, tracing

| Port | Provider | Required env |
|---|---|---|
| Storage | `sqlite` | `DB_PATH` |
| Storage | `postgres` | `DATABASE_URL`, `psycopg[binary]` |
| Cache | `json` | `CACHE_DIR` |
| Cache | `redis` | `REDIS_URL`, `redis` package |
| Tracing | `none` | none |
| Tracing | `langsmith` | `TRACING_PROVIDER=langsmith` or `LANGCHAIN_TRACING_V2=true`, plus LangSmith credentials |

## 3. Zero-key baseline

```dotenv
LLM_PROVIDER=openai-compatible
LLM_BASE_URL=http://localhost:11434/v1
LLM_MODEL=llama3.1
LLM_API_KEY=not-needed

EMBEDDINGS_PROVIDER=openai-compatible
EMBEDDINGS_BASE_URL=http://localhost:11434/v1
EMBEDDINGS_MODEL=nomic-embed-text

SEARCH_PROVIDER=duckduckgo
FETCH_PROVIDER=trafilatura
ANALYTICS_PROVIDER=csv
CRM_PROVIDER=csv
KEYWORD_PROVIDER=csv
PUBLISHING_PROVIDER=markdown
GEO_PROVIDER=none
STORAGE_PROVIDER=sqlite
CACHE_PROVIDER=json
TRACING_PROVIDER=none
```

## 4. Bank-style profile

```dotenv
LLM_PROVIDER=anthropic
LLM_MODEL=claude-sonnet-4-5
LLM_API_KEY=...

JUDGE_LLM_PROVIDER=gemini
JUDGE_LLM_MODEL=gemini-2.5-flash
JUDGE_LLM_API_KEY=...

SEARCH_PROVIDER=tavily
TAVILY_API_KEY=...
EMBEDDINGS_PROVIDER=local

ANALYTICS_PROVIDER=gsc
GSC_SITE_URL=...
GSC_SERVICE_ACCOUNT_JSON=...

CRM_PROVIDER=hubspot
HUBSPOT_API_KEY=...

GEO_PROVIDER=perplexity
PERPLEXITY_API_KEY=...

KEYWORD_PROVIDER=dataforseo
DATAFORSEO_LOGIN=...
DATAFORSEO_PASSWORD=...

PUBLISHING_PROVIDER=wordpress
WORDPRESS_BASE_URL=...
WORDPRESS_USER=...
WORDPRESS_APP_PASSWORD=...

STORAGE_PROVIDER=postgres
DATABASE_URL=...

REQUIRE_HUMAN_REVIEW=true
```

For a fully self-hosted perimeter, use `LLM_PROVIDER=openai-compatible` against an
internal vLLM/LiteLLM gateway, `EMBEDDINGS_PROVIDER=local`, and a self-hosted
WordPress/webhook publisher.

## 5. Adding a provider

1. Create one adapter file under `src/pexon/adapters/`, e.g.
   `llm_cohere.py`, implementing the relevant port.
2. Export `AVAILABLE` and `UNAVAILABLE_REASON` if the package is optional.
3. Add one `_spec(...)` line to the appropriate port dictionary in
   [registry.py](../src/pexon/adapters/registry.py).
4. Add the provider name to the `.env.example` comment; no `Settings` field is needed
   unless the provider has new configuration.
5. Run `./pexon inspect providers` and `./pexon doctor`.

No service, graph, subgraph or model changes are required.

## 6. Probe behavior

`pexon doctor` makes a cheap real call for every active port:

- LLM: one short completion;
- search: one-result query;
- fetch: HTTP status of the probe URL;
- embeddings: one short embedding;
- analytics/CRM/keywords: one read/query;
- GEO: one real engine query;
- publishing: read/auth check;
- storage: `SELECT 1`;
- cache: round-trip;
- tracing: client read.

Missing keys or unreachable services fail loudly. Inactive optional adapters are listed
by `pexon inspect providers`.
