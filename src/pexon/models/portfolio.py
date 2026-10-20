"""Keyword demand and portfolio-planning value objects."""
from __future__ import annotations

from datetime import UTC, datetime

from pydantic import Field

from pexon.models.base import FrozenModel


class KeywordDemand(FrozenModel):
    """Measured demand for one German keyword."""
    keyword: str
    volume: int = 0
    difficulty: float = 0.0
    cpc: float = 0.0
    intent: str = "informational"
    funnel_stage: str = "top"
    cluster: str = ""
    source: str = ""
    collected_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class PlanCandidate(FrozenModel):
    """A scored topic candidate in the content portfolio."""
    keyword: str
    topic_name_de: str
    cluster: str
    funnel_stage: str
    volume: int
    difficulty: float
    cpc: float
    priority: float
    covered: bool
    rationale: str


class ContentPlan(FrozenModel):
    """A demand-aware content plan."""
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    source: str
    candidates: tuple[PlanCandidate, ...]
    selected: tuple[PlanCandidate, ...]
    notes: str = ""
