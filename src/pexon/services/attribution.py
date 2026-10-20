"""Measure the business funnel: search -> leads -> pipeline -> clients."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from pexon.config.settings import Settings
from pexon.models.cost import CostBreakdown
from pexon.models.funnel import (
    AttributionRow,
    EconomicsReport,
    FunnelReport,
)
from pexon.ports.crm import CrmPort
from pexon.ports.storage import StoragePort
from pexon.services.audit import AuditLog
from pexon.services.economics import EconomicsService


class AttributionService:
    """Joins analytics and CRM data without storing personal data."""

    def __init__(
        self,
        settings: Settings,
        crm: CrmPort,
        storage: StoragePort,
        economics: EconomicsService,
        audit: AuditLog,
    ) -> None:
        self._settings = settings
        self._crm = crm
        self._storage = storage
        self._economics = economics
        self._audit = audit

    def build_report(
        self, run_id: str, *, since: datetime | None = None, until: datetime | None = None
    ) -> FunnelReport:
        """Build and persist one funnel report."""
        now = datetime.now(UTC)
        until = until or now
        since = since or (until - timedelta(days=self._settings.funnel_window_days))
        leads = self._crm.fetch_leads(since=since, until=until)
        performance = self._performance(since, until)
        articles = {row["id"]: row for row in self._storage.find("articles")}
        all_costs = self._economics.cost_by_article()
        clicks = sum(row["clicks"] for row in performance)
        impressions = sum(row["impressions"] for row in performance)
        by_article: dict[str, dict[str, float]] = {}
        for row in performance:
            item = by_article.setdefault(
                row["article_id"],
                {
                    "clicks": 0.0,
                    "impressions": 0.0,
                },
            )
            item["clicks"] += float(row["clicks"])
            item["impressions"] += float(row["impressions"])
        lead_by_article: dict[str, list] = {}
        for lead in leads.rows:
            if lead.article_id:
                lead_by_article.setdefault(lead.article_id, []).append(lead)
        active_ids = set(by_article) | set(lead_by_article)
        attributed_leads = sum(len(items) for items in lead_by_article.values())
        costs = {
            article_id: cost for article_id, cost in all_costs.items() if article_id in active_ids
        }
        attribution: list[AttributionRow] = []
        for article_id, metrics in by_article.items():
            article = articles.get(article_id, {})
            article_leads = lead_by_article.get(article_id, [])
            cost = costs.get(article_id)
            attribution.append(
                AttributionRow(
                    article_id=article_id,
                    title=str(article.get("title_de", "")),
                    impressions=metrics["impressions"],
                    clicks=metrics["clicks"],
                    leads=len(article_leads),
                    qualified_leads=sum(
                        1 for lead in article_leads if lead.status == "qualified" or lead.client
                    ),
                    clients=sum(1 for lead in article_leads if lead.client),
                    pipeline_value=sum(lead.annual_value for lead in article_leads),
                    won_value=sum(lead.won_value for lead in article_leads),
                    cost=cost.total_cost if cost else 0.0,
                )
            )
        attribution.sort(key=lambda row: (row.clients, row.leads, row.clicks), reverse=True)
        total_cost = sum(cost.total_cost for cost in costs.values())
        cost = CostBreakdown(
            llm_input_tokens=sum(c.llm_input_tokens for c in costs.values()),
            llm_output_tokens=sum(c.llm_output_tokens for c in costs.values()),
            search_calls=sum(c.search_calls for c in costs.values()),
            fetch_calls=sum(c.fetch_calls for c in costs.values()),
            llm_cost=round(sum(c.llm_cost for c in costs.values()), 6),
            search_cost=round(sum(c.search_cost for c in costs.values()), 6),
            fetch_cost=round(sum(c.fetch_cost for c in costs.values()), 6),
            fixed_cost=round(sum(c.fixed_cost for c in costs.values()), 6),
            total_cost=round(total_cost, 6),
            currency=self._settings.cost_currency,
        )
        economics = EconomicsReport(
            cost=cost,
            revenue=leads.won_value,
            leads=leads.leads,
            qualified_leads=leads.qualified,
            clients=leads.clients,
            cost_per_lead=_ratio(total_cost, leads.leads),
            cost_per_qualified_lead=_ratio(total_cost, leads.qualified),
            cost_per_client=_ratio(total_cost, leads.clients),
        )
        report = FunnelReport(
            since=since,
            until=until,
            impressions=impressions,
            clicks=clicks,
            leads=leads.leads,
            attributed_leads=attributed_leads,
            qualified_leads=leads.qualified,
            clients=leads.clients,
            pipeline_value=leads.pipeline_value,
            won_value=leads.won_value,
            lead_rate=_ratio(leads.leads, clicks),
            attribution_rate=_ratio(attributed_leads, leads.leads),
            qualified_rate=_ratio(leads.qualified, leads.leads),
            client_rate=_ratio(leads.clients, leads.qualified),
            attribution=tuple(attribution),
            economics=economics,
        )
        self._storage.write(
            "funnel_reports",
            {
                "id": f"funnel-{uuid.uuid4().hex[:12]}",
                "run_id": run_id,
                "since": since.isoformat(),
                "until": until.isoformat(),
                "report_json": report.model_dump(mode="json"),
                "created_at": now.isoformat(),
            },
        )
        self._audit.emit(
            run_id,
            "funnel_report",
            {
                "clicks": report.clicks,
                "leads": report.leads,
                "qualified_leads": report.qualified_leads,
                "clients": report.clients,
                "pipeline_value": report.pipeline_value,
                "cost": report.economics.cost.total_cost,
                "currency": report.economics.cost.currency,
            },
        )
        return report

    def _performance(self, since: datetime, until: datetime) -> list[dict]:
        rows = []
        for row in self._storage.find("performance"):
            try:
                measured = datetime.fromisoformat(
                    str(row.get("measured_at", "")).replace("Z", "+00:00")
                )
            except ValueError:
                continue
            if measured.tzinfo is None:
                measured = measured.replace(tzinfo=UTC)
            if since <= measured <= until:
                rows.append(row)
        return rows


def _ratio(numerator: float, denominator: float) -> float:
    return round(numerator / denominator, 6) if denominator else 0.0
