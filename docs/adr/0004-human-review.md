# ADR 0004 — Human review is a first-class gate

## Status

Accepted.

## Context

German bank content touches regulated claims. A model-based judge is useful but cannot
replace human accountability. Publishing automatically would create reputational risk.

## Decision

`REQUIRE_HUMAN_REVIEW=true` stages articles in `content/pending/` and stops the graph.
`pexon approve` records the reviewer, decision and notes, moves the file, updates the
frontmatter and refreshes the sitemap. Only then can measurement run.

Default is `false` for the zero-key demo; the bank profile enables it.

## Consequences

Positive:

- clear human accountability;
- review trail in `reviews` and `events`;
- no accidental publication of a staged draft.

Negative:

- breaks the fully automatic loop;
- adds an operational step;
- approval is CLI-only in this prototype.
