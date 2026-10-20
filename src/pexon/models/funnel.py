"""Leads, attribution and unit economics."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import Field

from pexon.models.base import FrozenModel
from pexon.models.cost import CostBreakdown


class Lead(FrozenModel):
    """One privacy-preserving CRM lead attributed to an article."""

    id: str
    article_id: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    source: str = ""
    medium: str = ""
    campaign: str = ""
    page_url: str = ""
    status: str = "new"
    company: str = ""
    annual_value: float = 0.0
    currency: str = "EUR"
    client: bool = False
    won_value: float = 0.0
    crm_url: str = ""
    provider: str = ""


class LeadBundle(FrozenModel):
    """Aggregated leads for a reporting window."""

    rows: tuple[Lead, ...]
    leads: int
    qualified: int
    clients: int
    pipeline_value: float
    won_value: float


class AttributionRow(FrozenModel):
    """Per-article funnel from search visibility to money."""

    article_id: str
    title: str
    impressions: float
    clicks: float
    leads: int
    qualified_leads: int
    clients: int
    pipeline_value: float
    won_value: float
    cost: float


class EconomicsReport(FrozenModel):
    """Cost and revenue per outcome."""

    cost: CostBreakdown
    revenue: float
    leads: int
    qualified_leads: int
    clients: int
    cost_per_lead: float
    cost_per_qualified_lead: float
    cost_per_client: float


class FunnelReport(FrozenModel):
    """Measured business funnel over a date window."""

    since: datetime
    until: datetime
    impressions: float
    clicks: float
    leads: int
    attributed_leads: int
    qualified_leads: int
    clients: int
    pipeline_value: float
    won_value: float
    lead_rate: float
    attribution_rate: float
    qualified_rate: float
    client_rate: float
    attribution: tuple[AttributionRow, ...]
    economics: EconomicsReport
