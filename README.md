<p align="center">
  <img src="docs/assets/architecture.svg" alt="Pexon architecture: four LangGraph content frames feeding a measurement plane for analytics, CRM, GEO and unit economics" width="100%">
</p>

<h1 align="center">Pexon</h1>

<p align="center">
  <strong>The content operating system for German bank AI consulting.</strong><br>
  Research → Intelligence → Generation → Reflection, with a closed loop from search visibility to clients.
</p>

<p align="center">
  <code>Python 3.11+</code> · <code>LangGraph 1.x</code> · <code>Pydantic v2</code> · <code>12 ports</code> · <code>33 adapters</code> · <code>SQLite checkpoints</code>
</p>

<p align="center">
  <a href="docs/CEO_BRIEF.md">CEO brief</a> ·
  <a href="docs/ARCHITECTURE.md">Architecture</a> ·
  <a href="docs/PROVIDER_MATRIX.md">Provider matrix</a> ·
  <a href="docs/OPERATIONS.md">Operations</a> ·
  <a href="docs/KPI_MODEL.md">KPI model</a> ·
  <a href="docs/DEMO.md">Demo</a>
</p>

---

## The one-sentence pitch

**Pexon turns a German bank AI topic into a researched, gated, SEO-ready article — then measures whether that article produced search visibility, AI-engine citations, qualified leads and consulting revenue.**

It is built as a four-frame LangGraph system, not a prompt chain. The graph is checkpointed, the services are provider-independent, and the measurement layer is deliberately honest: empty data stays empty.

> [!IMPORTANT]
> Pexon is a working architecture prototype, not a production platform. It has no auth, multi-tenancy, Docker, CI or monitoring stack. The measurement model is **observational**; causal holdout experiments are the next milestone.

---

## Why this exists

A consulting firm can publish a hundred AI articles and still learn nothing. The usual content stack optimises page views, not clients:

```text
publish → hope → report impressions → call it success
```

Pexon closes the loop:

```text
demand plan
   → research
   → generate
   → quality gate
   → publish
   → analytics + CRM + real GEO
   → funnel + unit economics
   → next content decision
```

The CEO gets four answers, not one dashboard:

| Question | Pexon answer |
|---|---|
| Did search visibility grow? | `FunnelReport` from GSC / Plausible / Matomo / CSV |
| Did AI answer engines mention or cite us? | `GeoReport` from Perplexity, OpenAI web search or Gemini grounding |
| Did visibility become business? | leads → qualified leads → clients → won value from CSV or HubSpot |
| Did the economics work? | `EconomicsReport`: cost per article, lead, qualified lead and client |

---

## Architecture at a glance

The diagram above is the system in one view: four content frames, one evidence plane,
one provider registry. Open the [architecture SVG](docs/assets/architecture.svg) for
full resolution or [the deep dive](docs/ARCHITECTURE.md) for every component.

### Four frames, one graph

```mermaid
flowchart LR
    START([Start]) --> R[Research]
    R --> I[Intelligence]
    I --> G[Generation]
    G -->|quality gate passed| P[Publish]
    G -->|failure + retries left| G
    G -->|retries exhausted| F[Failed]
    P -->|human review required| END([End])
    P --> M[Measure]
    M --> RF[Reflection]
    RF --> RP[Report]
    RP --> END
```

| Frame | Responsibility | Code |
|---|---|---|
| **Research** | Parallel German searches, fetch + sanitize, extract facts, judge-verify each fact, freeze ground truth | [subgraph](src/pexon/graph/subgraphs/research_subgraph.py) · [service](src/pexon/services/research_service.py) |
| **Intelligence** | SERP + engine-persona research, semantic dedupe, page features, champion–challenger learner, insights, drift | [subgraph](src/pexon/graph/subgraphs/intelligence_subgraph.py) · [service](src/pexon/services/intelligence_service.py) |
| **Generation** | Direction, `Send` fan-out, calibrated ranking, feature-gap refinement, re-rank, quality gate | [subgraph](src/pexon/graph/subgraphs/generation_subgraph.py) · [service](src/pexon/services/generation_service.py) |
| **Reflection** | Publish/stage, analytics, propose, prompt mutation, learner update | [subgraph](src/pexon/graph/subgraphs/reflection_subgraph.py) · [service](src/pexon/services/reflection_service.py) |

The top-level graph adds a final **Measurement Report** node that runs real GEO queries and joins CRM + analytics + cost data. See [pexon_graph.py](src/pexon/graph/pexon_graph.py).

---

## The business funnel

<p align="center">
  <img src="docs/assets/funnel.png" alt="Pexon business funnel from impressions to won value" width="100%">
</p>

The content gate still protects search quality. The **business layer** is separate and deliberately not reduced to a single score:

```text
impressions → clicks → leads → qualified leads → clients → won value
```

A traffic win with no qualified lead is visible as a failure. The funnel report includes attribution rate, qualified rate, client rate, per-article attribution, pipeline value, won value, cost per lead and cost per client.

Read the full measurement contract in [KPI_MODEL.md](docs/KPI_MODEL.md).

---

## What is real — and what is not

This repository is explicit about evidence. The architecture is impressive only if a reviewer can trust the labels.

| Capability | Status | Evidence |
|---|---|---|
| LLM generation | **Real** | OpenAI-compatible, Anthropic, Gemini adapters; no mock model |
| Search | **Real** | DuckDuckGo, Tavily, Brave, SerpAPI |
| Fetch | **Real** | Trafilatura, httpx, optional Playwright |
| Analytics | **Real** | GSC, Plausible, Matomo, CSV |
| CRM | **Real** | HubSpot, CSV |
| GEO | **Real when configured** | Perplexity, OpenAI web search, Gemini grounding; `none` by default |
| Keyword demand | **Real when configured** | DataForSEO, CSV |
| Publishing | **Real** | Markdown, WordPress REST, authenticated webhook |
| Learning | **Real** | Gradient boosting, time split, isotonic calibration, champion–challenger |
| Engine persona research | **Simulated by an LLM** | Useful competitive research, **never reported as GEO** |
| Causal impact | **Not proven** | Funnel is observational; holdout is the next milestone |

> [!NOTE]
> GEO defaults to `none` because there is no keyless, legitimate way to query a real AI answer engine. Pexon will not silently substitute a simulated answer.

---

## Quality gate

Every article passes a two-pass quality gate before it can leave Generation:

```text
PASS 1 · deterministic
  German language detection
  citation coverage against verified facts
  DSGVO / DORA / MaRisk / AI Act terms
  duplicate cosine against the existing corpus
  minimum article length

PASS 2 · independent judge
  factuality score + evidence
  compliance score + evidence
  German fluency score + evidence
```

Failures return concrete retry reasons to the direction node. The retry is a real LangGraph conditional edge, bounded by `MAX_RETRIES`. Failed runs are audited, not silently published.

Read [ARCHITECTURE.md](docs/ARCHITECTURE.md#quality-gate) for the full gate contract.

---

## Provider independence

The single most important design property:

> **Adding a provider must be one adapter file plus one registry line — never a change to a graph, subgraph or service.**

```text
graph ──▶ services ──▶ ports ◀── adapters
                         ▲
models (no dependencies) ─┘
```

`services/` imports only ports. `main.py` is the composition root. `adapters/registry.py` maps `(port, provider) → factory(settings)`.

### Ports and adapters

| Port | Default | Real alternatives | Selection |
|---|---|---|---|
| LLM | `openai-compatible` | Anthropic, Gemini | `LLM_PROVIDER` |
| Judge LLM | same as LLM | separate provider/model | `JUDGE_LLM_*` |
| Search | `duckduckgo` | Tavily, Brave, SerpAPI | `SEARCH_PROVIDER` |
| Fetch | `trafilatura` | httpx, Playwright | `FETCH_PROVIDER` |
| Embeddings | `openai-compatible` | local sentence-transformers | `EMBEDDINGS_PROVIDER` |
| Analytics | `csv` | GSC, Plausible, Matomo | `ANALYTICS_PROVIDER` |
| CRM | `csv` | HubSpot | `CRM_PROVIDER` |
| GEO | `none` | Perplexity, OpenAI, Gemini | `GEO_PROVIDER` |
| Keywords | `csv` | DataForSEO | `KEYWORD_PROVIDER` |
| Publishing | `markdown` | WordPress, webhook | `PUBLISHING_PROVIDER` |
| Storage | `sqlite` | Postgres | `STORAGE_PROVIDER` |
| Cache | `json` | Redis | `CACHE_PROVIDER` |
| Tracing | `none` | LangSmith | `TRACING_PROVIDER` |

The full adapter matrix, optional dependencies and probe behavior live in [PROVIDER_MATRIX.md](docs/PROVIDER_MATRIX.md).

---

## Quickstart: zero-key local stack

Requirements: Python 3.11+, [Ollama](https://ollama.com), and the two models pulled once.

```bash
cp .env.example .env
ollama pull llama3.1
ollama pull nomic-embed-text
ollama serve

./pexon doctor
./pexon plan --seeds "ai governance banken,lora fine-tuning" --write plan.yaml
./pexon run --topic "Claude Anthropic Governance für deutsche Banken" --wait 0
./pexon run --topic "LoRA-Fine-Tuning für deutsche Banken" --wait 0
./pexon report
```

The default stack is deliberately zero-key:

| Component | Default |
|---|---|
| LLM | Ollama `http://localhost:11434/v1` · `llama3.1` |
| Embeddings | Ollama · `nomic-embed-text` |
| Search | DuckDuckGo HTML |
| Fetch | Trafilatura with stdlib fallback |
| Analytics / CRM / Keywords | CSV headers in `data/` |
| GEO | `none` |
| Publishing | local Markdown |
| Storage | SQLite |
| Cache | JSON files |
| Tracing | none |

### Full installation

```bash
pip install -e ".[providers]"
```

The checked-in `./pexon` launcher also runs directly from `src/` before installation.

---

## Bank-style configuration

Only environment variables change. The same services, graph and subgraphs run inside a bank perimeter:

```dotenv
LLM_PROVIDER=anthropic
LLM_BASE_URL=https://api.anthropic.com
LLM_MODEL=claude-sonnet-4-5
LLM_API_KEY=sk-ant-...

JUDGE_LLM_PROVIDER=gemini
JUDGE_LLM_MODEL=gemini-2.5-flash
JUDGE_LLM_API_KEY=...

SEARCH_PROVIDER=tavily
TAVILY_API_KEY=tvly-...

EMBEDDINGS_PROVIDER=local

ANALYTICS_PROVIDER=gsc
GSC_SITE_URL=https://www.example-bank.de/
GSC_SERVICE_ACCOUNT_JSON=/path/inside/workspace/service-account.json

CRM_PROVIDER=hubspot
HUBSPOT_API_KEY=...
HUBSPOT_ARTICLE_PROPERTY=pexon_article_id

GEO_PROVIDER=perplexity
PERPLEXITY_API_KEY=pplx-...
GEO_BRAND_NAME=Example Bank Consulting
GEO_DOMAIN=www.example-bank.de

KEYWORD_PROVIDER=dataforseo
DATAFORSEO_LOGIN=...
DATAFORSEO_PASSWORD=...

PUBLISHING_PROVIDER=wordpress
WORDPRESS_BASE_URL=https://www.example-bank.de
WORDPRESS_USER=content-bot
WORDPRESS_APP_PASSWORD=...

STORAGE_PROVIDER=postgres
DATABASE_URL=postgresql://pexon:pexon@localhost:5432/pexon

REQUIRE_HUMAN_REVIEW=true
```

For a self-hosted bank deployment, point `LLM_BASE_URL` at vLLM, LiteLLM or an internal gateway and run the same graph. No code change is required.

Read [SECURITY_AND_COMPLIANCE.md](docs/SECURITY_AND_COMPLIANCE.md) before putting bank data through the system.

---

## CLI

```bash
pexon run --topic "..." [--wait 0] [--max-iterations N]
       [--llm openai-compatible|anthropic|gemini]
       [--search duckduckgo|tavily|brave|serpapi]
       [--analytics csv|gsc|plausible|matomo]
       [--target-keyword "..."] [--cluster "..."] [--funnel-stage middle]
       [--base-url URL] [--model NAME]

pexon run-batch --topics-file topics.example.yaml
pexon plan --seeds "ai governance banken,lora fine-tuning" --limit 10 --write plan.yaml
pexon report [--since 2026-01-01] [--until 2026-03-31]
pexon geo --topic "AI Governance für deutsche Banken"
pexon approve --article-id <id> --reviewer "Name" [--notes "..."]
pexon measure --article-id <id> [--wait 30]
pexon replay --run-id <id>
pexon inspect weights
pexon inspect features --article-id <id>
pexon inspect providers
pexon inspect settings
pexon seed-analytics --csv path.csv [--append]
pexon seed-leads --csv path.csv
pexon seed-keywords --csv path.csv
pexon evaluate --since 2026-01-01
pexon doctor
```

`pexon doctor` probes every active adapter with a cheap real call. A missing key fails loudly; only the documented CSV/Markdown paths are local. `pexon inspect settings` prints every threshold, its value and whether it came from the default, environment or CLI.

---

## The data contract

The repository ships header-only CSV files. No outcomes are fabricated.

`data/analytics.csv`
```csv
article_id,clicks,impressions,position,measured_at,page_url
```

`data/leads.csv`
```csv
lead_id,created_at,article_id,source,medium,campaign,page_url,status,company,annual_value,currency,client,won_value,crm_url
```

`data/keyword_demand.csv`
```csv
keyword,volume,difficulty,cpc,intent,funnel_stage,cluster
```

The first runs use `prior-v1`, a documented cold-start prior. Once `MIN_TRAINING_ROWS` real measured articles exist, the learner promotes a versioned model only if it beats the champion on both clicks and impressions MAE.

---

## What is auditable

- **Every run** has a `trace_id`, `run_id`, provider configuration and checkpointed graph state.
- **Every LLM call** goes through `LLMGateway`: PII redaction, token accounting, structured JSON validation and one corrective retry.
- **Every event** is append-only: searches, fallbacks, fetch failures, dropped facts, gates, retries, publishing, measurement, proposals, prompt variants and reports.
- **Every model** has a model card with MAE, R², features, row count, known limits and the provider configuration at training time.
- **Every replay** uses the same `thread_id`; completed nodes do not call the LLM again.

---

## Repository map

```text
pexon/
├── README.md                      # this page
├── pyproject.toml                 # package + dependencies
├── .env.example                   # every setting, zero-key and bank profiles
├── pexon                         # local launcher
├── docs/
│   ├── CEO_BRIEF.md               # non-technical business case
│   ├── ARCHITECTURE.md            # deep architecture and design decisions
│   ├── PROVIDER_MATRIX.md         # 12 ports, 33 adapters, how to add one
│   ├── OPERATIONS.md              # setup, run, review, replay, troubleshooting
│   ├── SECURITY_AND_COMPLIANCE.md # bank deployment checklist
│   ├── KPI_MODEL.md               # funnel, GEO, economics definitions
│   ├── DEMO.md                    # 10-minute CEO demo script
│   ├── ROADMAP.md                 # what comes after the prototype
│   ├── assets/
│   │   ├── architecture.svg/.png
│   │   ├── funnel.svg/.png
│   │   └── social-card.svg/.png
│   └── adr/                       # architecture decision records
├── CHANGELOG.md
├── CONTRIBUTING.md
├── SECURITY.md
├── LICENSE
├── db/
│   ├── schema.sql
│   └── pexon.db
├── data/
│   ├── analytics.csv
│   ├── leads.csv
│   └── keyword_demand.csv
├── content/
│   ├── posts/
│   └── pending/
└── src/pexon/
    ├── config/                    # Settings + German prompts
    ├── models/                    # Pydantic value objects
    ├── ports/                     # stable interfaces
    ├── adapters/                  # provider implementations + registry.py
    ├── guards/                    # sanitize, PII, language, JSON schema
    ├── observability/             # structured logging, metrics
    ├── services/                  # four frames + learner + measurement
    ├── graph/                     # state, top-level graph, four subgraphs, SQLite saver
    ├── cli.py
    └── main.py
```

---

## Design principles

1. **Depth, not volume.** Four frames, four services, four subgraphs. Extra complexity must buy learning, calibration, a guard or a measurable business outcome.
2. **No mocks.** Every adapter talks to a real service. Empty data is reported as empty, never synthesized.
3. **One registry.** A provider swap is configuration, not a code change in a service.
4. **Quality before reach.** The gate can fail an article; the graph can retry; the audit shows why.
5. **Business before vanity.** Impressions are a content signal; qualified leads and clients are the business signal.
6. **Honest evidence.** GEO is `none` unless a real engine is configured; causality is not claimed without a holdout.

---

## Documentation

| Document | What it answers |
|---|---|
| [CEO_BRIEF.md](docs/CEO_BRIEF.md) | Why should a CEO fund this? What is proven, what is next? |
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | How does the graph, state, checkpointing, learner and measurement work? |
| [PROVIDER_MATRIX.md](docs/PROVIDER_MATRIX.md) | Which providers exist, what do they need, how do I add one? |
| [OPERATIONS.md](docs/OPERATIONS.md) | How do I run, review, replay and troubleshoot it? |
| [SECURITY_AND_COMPLIANCE.md](docs/SECURITY_AND_COMPLIANCE.md) | What are the bank controls, PII flows, human review and deployment modes? |
| [KPI_MODEL.md](docs/KPI_MODEL.md) | How are SEO, GEO, funnel and unit economics defined? |
| [DEMO.md](docs/DEMO.md) | A 10-minute CEO demo script that does not fake data |
| [ROADMAP.md](docs/ROADMAP.md) | What is deliberately not in the prototype? |
| [ADR index](docs/adr/) | Why the major design decisions were made |
| [CHANGELOG.md](CHANGELOG.md) | What changed in v0.2 |
| [CONTRIBUTING.md](CONTRIBUTING.md) | How to preserve the architecture |
| [SECURITY.md](SECURITY.md) | How to report a vulnerability |

---

## Status

- **Prototype** — real adapters, real LangGraph, real learner, real SQLite replay.
- **No tests, Docker, CI, auth or monitoring stack** by design.
- **No live provider runs are bundled**; the repository is clean and starts with empty CSVs.
- **Causal holdout** is the next milestone; the measurement surface is ready for it.
- **License:** proprietary prototype; see [LICENSE](LICENSE).

If you are reviewing this as a CEO: start with [CEO_BRIEF.md](docs/CEO_BRIEF.md). If you are reviewing it as an engineer: start with [ARCHITECTURE.md](docs/ARCHITECTURE.md) and [PROVIDER_MATRIX.md](docs/PROVIDER_MATRIX.md).

---

<p align="center">
  <sub>Pexon · architecture prototype · German bank AI content · no fabricated analytics, no fabricated GEO, no hidden provider lock-in</sub>
</p>
