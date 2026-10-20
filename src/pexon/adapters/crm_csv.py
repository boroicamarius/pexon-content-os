"""CSV CRM adapter: the zero-key attribution path."""

from __future__ import annotations

import csv
from datetime import UTC, datetime
from pathlib import Path

from pexon.config.settings import Settings
from pexon.models.funnel import Lead, LeadBundle
from pexon.ports.crm import CrmPort
from pexon.ports.errors import AnalyticsError

AVAILABLE = True
UNAVAILABLE_REASON = ""
_COLUMNS = (
    "lead_id",
    "created_at",
    "article_id",
    "source",
    "medium",
    "campaign",
    "page_url",
    "status",
    "company",
    "annual_value",
    "currency",
    "client",
    "won_value",
    "crm_url",
)


class CsvCrm(CrmPort):
    """Reads a privacy-preserving lead export from data/leads.csv."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._path: Path = settings.leads_path

    @property
    def provider(self) -> str:
        return "csv"

    def fetch_leads(self, *, since: datetime, until: datetime) -> LeadBundle:
        """Filter CSV leads by creation date."""
        if not self._path.exists():
            return self._bundle([])
        rows: list[Lead] = []
        try:
            with self._path.open(newline="", encoding="utf-8") as handle:
                for item in csv.DictReader(handle):
                    created = self._parse_dt(item.get("created_at", ""))
                    if not (since <= created <= until):
                        continue
                    rows.append(
                        Lead(
                            id=item.get("lead_id") or item.get("id") or "",
                            article_id=item.get("article_id") or None,
                            created_at=created,
                            source=item.get("source") or "",
                            medium=item.get("medium") or "",
                            campaign=item.get("campaign") or "",
                            page_url=item.get("page_url") or "",
                            status=item.get("status") or "new",
                            company=item.get("company") or "",
                            annual_value=float(item.get("annual_value") or 0),
                            currency=item.get("currency") or "EUR",
                            client=str(item.get("client") or "").lower()
                            in {"1", "true", "yes", "ja"},
                            won_value=float(item.get("won_value") or 0),
                            crm_url=item.get("crm_url") or "",
                            provider=self.provider,
                        )
                    )
        except Exception as exc:
            raise AnalyticsError(f"csv crm read failed: {exc}") from exc
        return self._bundle(rows)

    def _bundle(self, rows: list[Lead]) -> LeadBundle:
        qualified = sum(1 for row in rows if row.status == "qualified" or row.client)
        clients = sum(1 for row in rows if row.client)
        return LeadBundle(
            rows=tuple(rows),
            leads=len(rows),
            qualified=qualified,
            clients=clients,
            pipeline_value=sum(row.annual_value for row in rows),
            won_value=sum(row.won_value for row in rows),
        )

    @staticmethod
    def _parse_dt(value: str) -> datetime:
        if not value:
            return datetime.now(UTC)
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)

    def probe(self) -> bool:
        """Verify the CSV header."""
        if not self._path.exists():
            raise AnalyticsError(f"missing CRM csv: {self._path}")
        with self._path.open(newline="", encoding="utf-8") as handle:
            header = next(csv.reader(handle), [])
        missing = [column for column in _COLUMNS[:8] if column not in header]
        if missing:
            raise AnalyticsError(f"CRM csv missing columns: {missing}")
        return True
