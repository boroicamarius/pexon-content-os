# Diagram assets

These diagrams are hand-authored SVG and rendered to PNG for environments that do not
render SVG in a README or slide deck.

| File | Purpose |
|---|---|
| `architecture.svg` / `.png` | hero architecture: four frames + evidence plane + guardrails + registry |
| `funnel.svg` / `.png` | business funnel: impressions to won value |
| `social-card.svg` / `.png` | GitHub social preview / slide cover |

Regenerate:

```bash
rsvg-convert -w 1600 architecture.svg -o architecture.png
rsvg-convert -w 1200 funnel.svg -o funnel.png
rsvg-convert -w 1280 social-card.svg -o social-card.png
```

The diagrams intentionally contain no fabricated numbers. They describe the evidence
model, not performance results.
