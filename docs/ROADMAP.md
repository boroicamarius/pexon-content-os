# Roadmap

Pexon deliberately stops at a sophisticated prototype. This roadmap separates what is
implemented from what a production bank platform and a causal pilot need.

## v0.2 — measurement layer (current)

Implemented:

- four frames as LangGraph subgraphs and services;
- checkpointed parent graph with retry, human review and report node;
- real provider adapters across 12 ports;
- research + judge-verified ground truth;
- `Send` fan-out generation;
- calibrated predictor and champion–challenger learner;
- two-pass quality gate;
- analytics, CRM, real GEO and cost measurement;
- demand-aware content plan;
- technical SEO, sitemap, robots and three publishing targets;
- human review staging and approval;
- append-only audit, metrics, tracing and replay.

## v0.3 — causal pilot

Not implemented yet:

1. **Holdout assignment** at topic-cluster or market level.
2. **Query-level GSC** ingestion (query, page, clicks, impressions, position).
3. **Rank tracking** for a fixed target query set.
4. **Content decay** detection and refresh recommendations.
5. **Pre/post + treatment/control** report with uncertainty.
6. **Lead quality scoring** from sales, not only CRM stage.
7. **Per-provider cost tables**, including GEO and CRM contract fees.
8. **Content portfolio optimization** under budget and editorial capacity.

## v0.4 — bank production

- authentication and role-based approval;
- Postgres migrations and backup automation;
- secrets manager integration;
- retention and deletion policy;
- SIEM/OTel export;
- signed audit trail;
- CMS field mapping for bank design system;
- SSO and editorial workflow;
- DLP integration;
- formal threat model.

## v1.0 — operating product

- multi-tenant client workspaces;
- shared topic/entity graph;
- content calendar and capacity planning;
- sales loop integration (CRM stages and opportunity outcomes);
- causal experimentation service;
- model registry with rollback;
- provider A/B testing by traffic or market.

## Explicit non-goals for this prototype

| Non-goal | Why |
|---|---|
| Docker/Kubernetes | deployability is not the current risk |
| CI pipeline | no test suite by design; manual verification |
| auth/multi-tenancy | single trusted operator |
| Prometheus/Grafana/OTel | metrics are printed and persisted; not a monitoring stack |
| message queue | synchronous graph is sufficient |
| automatic refit on drift | drift is detected, not auto-applied |
| simulated GEO | would undermine the evidence |
| fabricated analytics | would undermine the business case |

## Definition of a successful pilot

A pilot is successful if it produces credible answers, not just content:

- at least one measured content cohort;
- a clear cost per qualified lead;
- a GEO baseline and a repeated measurement;
- a champion model that beats the prior on a time-based test;
- a decision to scale, narrow or stop based on data.

If the answer is “stop”, the architecture has still done its job.
