# Operations

This is the operator runbook for the prototype. It assumes the repository is the working
directory.

## 1. Prerequisites

- Python 3.11+
- Ollama for the zero-key LLM path
- Optional provider keys for the bank profile
- No Docker, database server or queue for the default path

## 2. Install

### Local launcher, no package install

```bash
cp .env.example .env
./pexon doctor
```

The checked-in `pexon` script adds `src/` to `PYTHONPATH` and runs `python -m pexon`.

### Editable package

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[providers]"
pexon doctor
```

## 3. Ollama baseline

```bash
ollama pull llama3.1
ollama pull nomic-embed-text
ollama serve
```

`.env`:

```dotenv
LLM_PROVIDER=openai-compatible
LLM_BASE_URL=http://localhost:11434/v1
LLM_MODEL=llama3.1
LLM_API_KEY=not-needed

EMBEDDINGS_PROVIDER=openai-compatible
EMBEDDINGS_BASE_URL=http://localhost:11434/v1
EMBEDDINGS_MODEL=nomic-embed-text
```

Run `./pexon doctor`. It must reach the LLM, judge, search, fetch, embeddings, analytics,
CRM, GEO, keyword, publishing, storage, cache and trace probes. In the zero-key profile
GEO is `none` and therefore has no external call.

## 4. First run

```bash
./pexon plan --seeds "ai governance banken,lora fine-tuning" --write plan.yaml
./pexon run-batch --topics-file plan.yaml
```

For one topic:

```bash
./pexon run \
  --topic "Claude Anthropic Governance für deutsche Banken" \
  --target-keyword "claude anthropic governance banken" \
  --cluster governance \
  --funnel-stage middle \
  --wait 0
```

`--wait 0` deliberately skips analytics and marks `pending_measure`. Use it when the
article has just been published.

## 5. Human review

```dotenv
REQUIRE_HUMAN_REVIEW=true
```

With review enabled, `publish` writes to `content/pending/<slug>.md` and records
`status=pending_review`. The graph ends there without measuring.

Approve:

```bash
./pexon approve \
  --article-id art-... \
  --reviewer "Compliance Lead" \
  --notes "DORA references checked"
```

The article moves to `content/posts/`, frontmatter is updated, a `reviews` row is
written and the sitemap is refreshed.

Then measure:

```bash
./pexon measure --article-id art-... --wait 30
./pexon report
```

## 6. Measurement

### Analytics

`ANALYTICS_WINDOW_DAYS` controls the collection window. Supported:

- CSV (`data/analytics.csv`, zero-key);
- GSC;
- Plausible;
- Matomo.

### CRM

`CRM_PROVIDER=csv` reads `data/leads.csv`. `CRM_PROVIDER=hubspot` uses the HubSpot v3
search API and custom properties. Set:

```dotenv
HUBSPOT_ARTICLE_PROPERTY=pexon_article_id
HUBSPOT_PIPELINE_PROPERTY=pexon_pipeline_value
HUBSPOT_WON_PROPERTY=pexon_won_value
```

At minimum, every lead must carry an article ID to be attributable.

### GEO

```dotenv
GEO_PROVIDER=perplexity   # or openai, gemini
PERPLEXITY_API_KEY=...
GEO_BRAND_NAME=Example Bank Consulting
GEO_DOMAIN=www.example-bank.de
```

`GEO_QUERY_COUNT` controls the German query set. Results land in `geo_visibility` and
the report exposes mention and citation rates.

### Economics

Set actual contract rates:

```dotenv
LLM_INPUT_COST_PER_1K=...
LLM_OUTPUT_COST_PER_1K=...
SEARCH_COST_PER_CALL=...
FETCH_COST_PER_CALL=...
ARTICLE_FIXED_COST=...
COST_CURRENCY=EUR
```

Cost is recorded per article at publication. GEO/CRM contract fees are not inferred;
fold them into `ARTICLE_FIXED_COST` if needed.

## 7. Inspect

```bash
./pexon inspect providers
./pexon inspect settings
./pexon inspect weights
./pexon inspect features --article-id art-...
```

`inspect settings` prints the value, source (`default|env|cli`) and masks secrets.

## 8. Replay

```bash
./pexon replay --run-id run-...
```

Replay uses the same `thread_id`. Completed nodes are not re-executed and no second LLM
call is made. Pending nodes resume.

Replay is useful for auditing what the graph saw. It is not a time machine for external
providers: if a pending node calls a provider, it will do so again.

## 9. Data operations

### Analytics

```bash
./pexon seed-analytics --csv exports/gsc.csv
```

### Leads

```bash
./pexon seed-leads --csv exports/hubspot.csv
```

### Keyword demand

```bash
./pexon seed-keywords --csv exports/keywords.csv
```

The seed commands copy rows into `data/` and preserve empty files as headers only.

## 10. Backup and retention

- Back up `db/pexon.db` and `content/`.
- `.cache/` is disposable.
- `events` is append-only; do not edit it manually.
- The prototype does not implement retention policies. A bank deployment should define
  retention for prompts, source text, article content and audit events.

## 11. Troubleshooting

| Symptom | Likely cause | Action |
|---|---|---|
| `doctor` LLM fails | Ollama not running, wrong base URL, model not pulled | `ollama serve`, check `LLM_BASE_URL`, pull model |
| `doctor` search fails | network/key/bot challenge | switch provider or add key |
| `doctor` embeddings fails | `nomic-embed-text` missing | `ollama pull nomic-embed-text` |
| `doctor` GEO fails | no key or invalid engine model | configure `GEO_*`, or leave `none` |
| `pending_measure` | no analytics rows in window | seed CSV or verify GSC access |
| `no features for article` | article never reached publish | inspect run events |
| Gate fails on judge | judge provider unavailable or low score | inspect event payload, improve draft or provider |
| Duplicate gate fails | embedding provider unavailable | restore embeddings; gate fails closed |
| Weights stay `prior-v1` | fewer than `MIN_TRAINING_ROWS` measured rows | publish and measure more |
| Learner rejects | challenger did not beat champion on both targets | inspect model card/event; collect more data |
| Review stuck | `require_human_review=true` | use `approve` |

## 12. Operational limits

- No authentication; do not expose the CLI/service to untrusted users.
- No per-user rate limiting beyond SDK defaults.
- SQLite is single-machine; Postgres is the multi-user option.
- Checkpoint and application data share a database by default.
- No automatic schema migrations; `schema.sql` is idempotent for new databases.
- No background scheduler; batch runs are foreground.
