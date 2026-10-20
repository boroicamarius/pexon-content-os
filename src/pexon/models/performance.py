"""Measured performance value objects."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import Field

from pexon.models.base import FrozenModel


class Performance(FrozenModel):
    """Analytics facts for one article and window."""

    article_id: str
    clicks: float
    impressions: float
    position: float
    measured_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    source: str = ""
    page_url: str = ""


class PerformanceBundle(FrozenModel):
    """Aggregated measured performance for an article."""

    article_id: str
    rows: tuple[Performance, ...]
    clicks: float
    impressions: float
    position: float
