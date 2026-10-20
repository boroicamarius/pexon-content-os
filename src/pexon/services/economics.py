"""Unit economics from real token, search and fetch usage."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pexon.config.settings import Settings
from pexon.models.cost import CostBreakdown
from pexon.observability.metrics import MetricsCollector
from pexon.ports.storage import StoragePort

_UNIT = 1000.0


class EconomicsService:
    """Turns runtime metrics into auditable cost and unit economics."""

    def __init__(self, settings: Settings, metrics: MetricsCollector,
                 storage: StoragePort | None = None) -> None:
        self._settings = settings
        self._metrics = metrics
        self._storage = storage

    def breakdown(self) -> CostBreakdown:
        """Compute the run cost from measured counters and configured rates."""
        snapshot = self._metrics.snapshot()
        tokens_in = int(snapshot["tokens_in"])
        tokens_out = int(snapshot["tokens_out"])
        searches = int(snapshot["search_calls"])
        fetches = int(snapshot["fetch_ok"])
        llm_cost = (
            tokens_in / _UNIT * self._settings.llm_input_cost_per_1k
            + tokens_out / _UNIT * self._settings.llm_output_cost_per_1k
        )
        search_cost = searches * self._settings.search_cost_per_call
        fetch_cost = fetches * self._settings.fetch_cost_per_call
        total = llm_cost + search_cost + fetch_cost + self._settings.article_fixed_cost
        return CostBreakdown(
            llm_input_tokens=tokens_in,
            llm_output_tokens=tokens_out,
            search_calls=searches,
            fetch_calls=fetches,
            llm_cost=round(llm_cost, 6),
            search_cost=round(search_cost, 6),
            fetch_cost=round(fetch_cost, 6),
            fixed_cost=round(self._settings.article_fixed_cost, 6),
            total_cost=round(total, 6),
            currency=self._settings.cost_currency,
        )

    def record_article_cost(self, article_id: str, run_id: str) -> CostBreakdown:
        """Persist the run cost against the published article."""
        cost = self.breakdown()
        if self._storage is not None:
            self._storage.write("article_costs", {
                "id": f"cost-{article_id}",
                "article_id": article_id,
                "run_id": run_id,
                "llm_input_tokens": cost.llm_input_tokens,
                "llm_output_tokens": cost.llm_output_tokens,
                "search_calls": cost.search_calls,
                "fetch_calls": cost.fetch_calls,
                "llm_cost": cost.llm_cost,
                "search_cost": cost.search_cost,
                "fetch_cost": cost.fetch_cost,
                "fixed_cost": cost.fixed_cost,
                "total_cost": cost.total_cost,
                "currency": cost.currency,
                "created_at": datetime.now(UTC).isoformat(),
            })
        return cost

    def cost_by_article(self) -> dict[str, CostBreakdown]:
        """Read persisted article costs for attribution reports."""
        if self._storage is None:
            return {}
        result: dict[str, CostBreakdown] = {}
        for row in self._storage.find("article_costs"):
            result[str(row["article_id"])] = CostBreakdown(
                llm_input_tokens=int(row.get("llm_input_tokens", 0)),
                llm_output_tokens=int(row.get("llm_output_tokens", 0)),
                search_calls=int(row.get("search_calls", 0)),
                fetch_calls=int(row.get("fetch_calls", 0)),
                llm_cost=float(row.get("llm_cost", 0.0)),
                search_cost=float(row.get("search_cost", 0.0)),
                fetch_cost=float(row.get("fetch_cost", 0.0)),
                fixed_cost=float(row.get("fixed_cost", 0.0)),
                total_cost=float(row.get("total_cost", 0.0)),
                currency=str(row.get("currency", self._settings.cost_currency)),
            )
        return result

    def summary(self) -> dict[str, Any]:
        """JSON-safe cost summary for CLI output."""
        cost = self.breakdown()
        return cost.model_dump(mode="json")
