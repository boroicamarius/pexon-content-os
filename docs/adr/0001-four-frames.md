# ADR 0001 — Four frames as subgraphs and services

## Status

Accepted.

## Context

The CEO's architecture has four named frames: Research, Generation, Intelligence and
Reflection. A single monolithic content pipeline would be easier to write but would
hide ownership, make provider swaps invasive and reduce auditability.

## Decision

Each frame is:

- a LangGraph subgraph;
- a plain-Python service;
- composed by a parent graph.

The parent owns sequencing, retries, review routing, measurement and report generation.

## Consequences

Positive:

- frames can be understood and reviewed independently;
- a failure is visible as a graph transition;
- the four CEO concepts survive in code and documentation;
- services remain testable without the graph.

Negative:

- more files and explicit wiring;
- state must be shared through a typed state object;
- parent/subgraph composition adds conceptual overhead.

## Alternatives rejected

- One large graph: hides frame boundaries.
- Four microservices: operational overhead not justified for a prototype.
- A single `ContentPipeline` class: loses the architecture's language.
