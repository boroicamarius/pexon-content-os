"""HubSpot CRM adapter for real lead and pipeline attribution."""

from __future__ import annotations

from datetime import UTC, datetime

import httpx

from pexon.config.settings import Settings
from pexon.models.funnel import Lead, LeadBundle
from pexon.ports.crm import CrmPort
from pexon.ports.errors import AnalyticsError

AVAILABLE = True
UNAVAILABLE_REASON = ""
_API = "https://api.hubapi.com"


class HubSpotCrm(CrmPort):
    """Reads contacts and custom pipeline values from HubSpot CRM v3."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._key = settings.hubspot_api_key.get_secret_value() if settings.hubspot_api_key else ""

    @property
    def provider(self) -> str:
        return "hubspot"

    def fetch_leads(self, *, since: datetime, until: datetime) -> LeadBundle:
        """Page through real HubSpot contacts in the date window."""
        if not self._key:
            raise AnalyticsError("HUBSPOT_API_KEY is required for hubspot")
        properties = [
            "createdate",
            "lifecyclestage",
            "hs_analytics_source",
            "hs_analytics_first_url",
            "annualrevenue",
            "company",
            self._settings.hubspot_article_property,
            self._settings.hubspot_pipeline_property,
            self._settings.hubspot_won_property,
        ]
        body: dict[str, object] = {
            "limit": 100,
            "properties": properties,
            "filterGroups": [
                {
                    "filters": [
                        {
                            "propertyName": "createdate",
                            "operator": "BETWEEN",
                            "value": int(since.timestamp() * 1000),
                            "highValue": int(until.timestamp() * 1000),
                        }
                    ]
                }
            ],
        }
        rows: list[Lead] = []
        after: str | None = None
        try:
            while True:
                if after:
                    body["after"] = after
                response = httpx.post(
                    f"{_API}/crm/v3/objects/contacts/search",
                    headers={
                        "Authorization": f"Bearer {self._key}",
                        "content-type": "application/json",
                    },
                    json=body,
                    timeout=self._settings.crm_timeout_seconds,
                )
                response.raise_for_status()
                data = response.json()
                for item in data.get("results", []):
                    rows.append(self._contact_to_lead(item))
                after = data.get("paging", {}).get("next", {}).get("after")
                if not after:
                    break
        except Exception as exc:
            raise AnalyticsError(f"hubspot query failed: {exc}") from exc
        qualified = sum(1 for row in rows if row.status == "qualified" or row.client)
        return LeadBundle(
            rows=tuple(rows),
            leads=len(rows),
            qualified=qualified,
            clients=sum(1 for row in rows if row.client),
            pipeline_value=sum(row.annual_value for row in rows),
            won_value=sum(row.won_value for row in rows),
        )

    def _contact_to_lead(self, item: dict) -> Lead:
        props = item.get("properties", {})
        stage = str(props.get("lifecyclestage") or "").lower()
        client = stage in {"customer", "evangelist"}
        qualified = stage in {"opportunity", "salesqualifiedlead", "qualifiedtobuy", "customer"}
        created = props.get("createdate") or datetime.now(UTC).isoformat()
        created_at = datetime.fromisoformat(str(created).replace("Z", "+00:00"))
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=UTC)
        return Lead(
            id=str(item.get("id", "")),
            article_id=props.get(self._settings.hubspot_article_property) or None,
            created_at=created_at,
            source=str(props.get("hs_analytics_source") or ""),
            page_url=str(props.get("hs_analytics_first_url") or ""),
            status="qualified" if qualified else ("client" if client else "new"),
            company=str(props.get("company") or ""),
            annual_value=_number(props.get(self._settings.hubspot_pipeline_property)),
            client=client,
            won_value=_number(props.get(self._settings.hubspot_won_property)),
            crm_url=f"https://app.hubspot.com/contacts/{item.get('id', '')}",
            provider=self.provider,
        )

    def probe(self) -> bool:
        """Read one contact through the real API."""
        if not self._key:
            raise AnalyticsError("HUBSPOT_API_KEY is required for hubspot")
        response = httpx.get(
            f"{_API}/crm/v3/objects/contacts",
            headers={"Authorization": f"Bearer {self._key}"},
            params={"limit": 1},
            timeout=self._settings.crm_timeout_seconds,
        )
        response.raise_for_status()
        return True


def _number(value: object) -> float:
    try:
        return float(str(value or 0))
    except ValueError:
        return 0.0
