# KPI model

Pexon separates three questions that dashboards usually collapse:

1. **Content quality** — did we make a good, compliant article?
2. **Discovery** — did search and AI engines surface it?
3. **Business** — did it produce qualified demand and revenue?

## 1. Content quality

| Gate | Meaning | Threshold |
|---|---|---|
| `lang` | German detection | `GERMAN_MIN_SCORE` |
| `citation` | verified citations / total citations | `CITATION_COVERAGE_MIN`, `MIN_CITATIONS` |
| `compliance` | presence of configured regulatory terms | `COMPLIANCE_MIN_MATCHES` |
| `duplicate` | cosine similarity to existing corpus | `DUP_SIM_THRESHOLD` |
| `length` | minimum words | `MIN_ARTICLE_WORDS` |
| `judge_factuality` | judge score | `JUDGE_FACTUALITY_MIN` |
| `judge_compliance` | judge score | `JUDGE_COMPLIANCE_MIN` |
| `judge_fluency` | judge score | `JUDGE_FLUENCY_MIN` |

The gate is pass/fail. Failure reasons return to generation. The retry is bounded.

## 2. Search discovery

`AnalyticsPort` provides page-level metrics:

| Field | Definition |
|---|---|
| `impressions` | search result impressions for the page/window |
| `clicks` | clicks for the page/window |
| `position` | impressions-weighted average position |

Derived:

```text
CTR = clicks / impressions
```

The learner predicts clicks and impressions separately. The gate removes samples whose
**lower confidence bound** misses `BASELINE_CLICKS` or `BASELINE_IMPRESSIONS`.

## 3. GEO visibility

GEO is measured by real answer engines, not by the generator's role-play.

For each configured query:

```text
brand_mentioned = brand name appears in the answer or citations
domain_cited    = owned domain appears in citations or answer text
```

Aggregated:

```text
mention_rate  = queries with brand mention / queries
citation_rate = queries with owned-domain citation / queries
```

`GeoReport` is stored separately from search analytics. A query set is deliberately
fixed so the same measurement can be repeated over time. Change the query set only with
a new baseline.

## 4. Business funnel

```text
impressions
  → clicks
  → leads
  → qualified leads
  → clients
  → won value
```

Derived:

```text
lead_rate        = leads / clicks
attribution_rate = attributed_leads / leads
qualified_rate   = qualified_leads / leads
client_rate      = clients / qualified_leads
```

`attributed_leads` counts leads with an `article_id`; `leads` includes all CRM leads in
the window. This distinction prevents unattributed CRM activity from being silently
credited to content.

## 5. Unit economics

```text
content_cost = llm_cost + search_cost + fetch_cost + fixed_cost
cost_per_lead = content_cost / leads
cost_per_qualified_lead = content_cost / qualified_leads
cost_per_client = content_cost / clients
revenue = won_value
```

Cost is recorded per article at publication. GEO/CRM contract fees are not inferred; put
them in `ARTICLE_FIXED_COST` if they must be included.

## 6. Content planning

`pexon plan` scores:

```text
volume_score = min(1, volume / PLAN_VOLUME_CEILING)
difficulty_factor = 1 - min(difficulty, PLAN_DIFFICULTY_SCALE) / PLAN_DIFFICULTY_SCALE
coverage_factor = PLAN_COVERAGE_PENALTY if covered else 1
priority = volume_score × intent_weight × funnel_weight
           × difficulty_factor × coverage_factor × PLAN_CTR
```

Intent and funnel weights are configurable maps. The score is a **planning aid**, not a
guarantee. It does not replace sales judgement.

## 7. Executive scorecard

| Question | Metric | Report |
|---|---|---|
| Are we publishing at quality? | first-pass gate rate, retries/article | events, gates |
| Are we earning search visibility? | impressions, clicks, CTR, position | `FunnelReport` |
| Are we earning AI citations? | mention rate, citation rate | `GeoReport` |
| Are we producing demand? | leads, attributed leads, qualified rate | `FunnelReport` |
| Are we producing clients? | client rate, pipeline, won value | `FunnelReport` |
| Is the economics viable? | cost/lead, cost/qualified lead, cost/client | `EconomicsReport` |
| Is the model learning? | champion MAE, R², promotion rate | model cards |
| Is the portfolio healthy? | coverage, priority, content decay | `ContentPlan` |

## 8. What the numbers do not prove

The funnel is observational. It cannot separate content impact from seasonality, brand,
sales activity, PR or market shifts.

To establish causality, run a holdout or matched-market experiment:

- pre-register the primary outcome (qualified leads);
- randomise matched topic clusters into treatment and holdout;
- keep the assignment fixed for the measurement window;
- compare treatment vs holdout, not before vs after alone;
- report uncertainty, not a single percentage.

This is the next architecture milestone, not a claim made by the current prototype.

## 9. Targets

No revenue or lead targets are hardcoded. They depend on the consultancy's market,
average deal size, sales capacity and content budget. Set them with the sponsor before
the pilot and store them outside the codebase.
