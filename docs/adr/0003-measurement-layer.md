# ADR 0003 — Measure business outcomes, not only clicks

## Status

Accepted.

## Context

The first prototype defined quality as clicks + impressions. That is a useful content
proxy, but the CEO's goal is consulting clients. A system that optimises traffic can
succeed on its own metric while failing commercially.

## Decision

Keep clicks + impressions as the pre-publication ranking/gate signal, and add a separate
measurement plane:

- `FunnelReport` joins analytics, CRM and costs;
- `GeoReport` measures real AI-answer visibility;
- `EconomicsReport` computes cost per lead/client;
- the parent graph runs a `report` node after reflection.

GEO measurement is real-engine only. `GEO_PROVIDER=none` is explicit.

## Consequences

Positive:

- traffic and business outcomes are both visible;
- a high-traffic/no-lead article is a visible failure;
- the CEO can see cost per outcome;
- the system is ready for a holdout experiment.

Negative:

- more external integrations and credentials;
- attribution depends on CRM hygiene;
- causal claims still require a separate experiment design.

## What was deliberately not done

No synthetic CRM data, no fake GEO citations and no invented revenue. Empty data remains
empty.
