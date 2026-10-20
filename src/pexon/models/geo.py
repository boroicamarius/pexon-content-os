"""Real generative-engine visibility value objects."""
from __future__ import annotations

from datetime import UTC, datetime

from pydantic import Field

from pexon.models.base import FrozenModel


class GeoQueryResult(FrozenModel):
    """One measured answer-engine response for one query."""
    engine: str
    query: str
    answer_excerpt: str
    citation_urls: tuple[str, ...] = ()
    brand_mentioned: bool = False
    domain_cited: bool = False
    measured_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class GeoReport(FrozenModel):
    """Aggregated AI-answer visibility for a topic or article."""
    topic_id: str
    article_id: str | None = None
    brand: str
    domain: str
    provider: str
    enabled: bool
    results: tuple[GeoQueryResult, ...] = ()
    mention_rate: float = 0.0
    citation_rate: float = 0.0
    measured_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
