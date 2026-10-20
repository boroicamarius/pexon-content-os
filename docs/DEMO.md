# Demo guide

This is the 10-minute walkthrough for a CEO or investment committee. Do not show
fabricated analytics or GEO citations. The point of the demo is the operating loop and
the honesty of the measurement.

## Before the room

```bash
cp .env.example .env
ollama pull llama3.1
ollama pull nomic-embed-text
ollama serve
./pexon doctor
```

If Ollama is not available, show the architecture and the provider matrix, not a fake
run.

Optional bank-mode demo:

```dotenv
LLM_PROVIDER=anthropic
SEARCH_PROVIDER=tavily
ANALYTICS_PROVIDER=gsc
CRM_PROVIDER=hubspot
GEO_PROVIDER=perplexity
PUBLISHING_PROVIDER=wordpress
REQUIRE_HUMAN_REVIEW=true
```

## Minute 1 — the thesis

Open the README architecture image.

> “Most content systems optimise impressions. Pexon optimises from demand to a qualified
> consulting conversation, and it refuses to invent the evidence.”

Point at the four frames and the evidence plane.

## Minute 2 — the four frames

Open [ARCHITECTURE.md](ARCHITECTURE.md#the-four-frames).

- Research: verified ground truth.
- Intelligence: competitor + learner.
- Generation: samples, ranking, quality gate.
- Reflection: publish, measure, mutate.

Emphasise that these are real subgraphs and services, not a prompt chain.

## Minute 3 — the flexibility contract

```bash
./pexon inspect providers
./pexon inspect settings | head -40
```

Show the 12 ports and 33 adapters. Point out `GEO_PROVIDER=none` and say why: no
keyless, legitimate AI-engine measurement.

## Minute 4 — plan

```bash
./pexon plan --seeds "ai governance banken,lora fine-tuning" --write plan.yaml
```

Show that the plan is demand-aware when a real keyword source is configured, and
explicitly “unmeasured” when it is not.

## Minute 5 — run

```bash
./pexon run --topic "Claude Anthropic Governance für deutsche Banken" --wait 0
```

Show:

- research facts and gate decisions;
- samples and CIs;
- the quality gate;
- the Markdown article;
- `pending_measure` if waiting zero.

## Minute 6 — the article

Open `content/posts/<slug>.md`.

Show:

- German article;
- YAML frontmatter;
- canonical;
- JSON-LD;
- internal links;
- expected clicks/impressions with CIs.

## Minute 7 — the evidence report

```bash
./pexon report
```

Explain:

- funnel rates;
- attribution rate;
- cost per lead;
- why a traffic-only win is not called success.

If real GSC/CRM data is connected, show it. Otherwise say the file is header-only and
the report is empty.

## Minute 8 — GEO

```bash
./pexon geo --topic "AI Governance für deutsche Banken"
```

With `GEO_PROVIDER=none`, it returns no report. That is the point: the system does not
role-play a citation. With a configured engine, show mention and citation rates.

## Minute 9 — human review

```bash
./pexon approve --article-id art-... --reviewer "Compliance Lead"
./pexon measure --article-id art-... --wait 30
```

Show the pending file, review row and post-approval measurement.

## Minute 10 — the ask

> “Fund a measurement-first pilot: 15–25 articles, a real CRM baseline, a real GEO
> baseline, and a holdout design. If qualified leads and AI citations do not move, the
> system tells us early.”

## Demo anti-patterns

Do not:

- seed analytics with fake clicks;
- show a simulated engine answer as a GEO citation;
- call traffic “clients”;
- show a model card without the provider configuration;
- hide that human review is required for bank content.
