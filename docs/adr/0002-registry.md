# ADR 0002 — Registry-based provider independence

## Status

Accepted.

## Context

Services must run against Ollama, Anthropic, Gemini, DuckDuckGo, Tavily, GSC, HubSpot,
Perplexity, WordPress, Postgres and others. Importing concrete adapters into services
would make every provider swap a service change.

## Decision

Every external dependency is a port. `adapters/registry.py` maps a provider name to a
factory. The composition root builds the active adapter from settings. Services receive
ports, never adapters.

## Consequences

Positive:

- a provider is one adapter file + one registry line;
- zero-key and bank profiles use the same services;
- optional packages can be marked unavailable without breaking imports;
- provider A/B tests are environment changes.

Negative:

- one more indirection;
- registry is a central file that must be maintained;
- dynamic imports delay some type errors to runtime.

## Guardrails

- services must not import `pexon.adapters.*` concrete modules;
- optional packages must expose `AVAILABLE` and `UNAVAILABLE_REASON`;
- `pexon doctor` probes the active adapter, not a fallback.
