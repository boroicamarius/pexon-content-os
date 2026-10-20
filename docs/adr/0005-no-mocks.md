# ADR 0005 — No mocks in the product path

## Status

Accepted.

## Context

Demo systems often ship `FakeLLM`, seeded analytics and deterministic sample articles.
They look complete but teach nothing about provider behaviour, failure modes or real
economics.

## Decision

The production path contains no mock adapters. Every adapter either:

- talks to a real service;
- reads a real local file (CSV / Markdown);
- or is an explicit no-op that reports “not measured” (GEO none, tracing none).

Empty data stays empty. Missing keys fail loudly in `doctor`.

## Consequences

Positive:

- provider behaviour is real;
- failure handling is real;
- the business case is not flattered by synthetic data.

Negative:

- the demo requires Ollama or keys;
- there is no offline “happy path” with fabricated articles;
- reviewers must configure the environment to see a full run.
