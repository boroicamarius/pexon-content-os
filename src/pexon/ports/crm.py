"""CRM / lead attribution port."""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from pexon.models.funnel import LeadBundle


class CrmPort(ABC):
    """Read privacy-preserving leads for result attribution."""

    @property
    @abstractmethod
    def provider(self) -> str:
        """Registered provider name."""

    @abstractmethod
    def fetch_leads(self, *, since: datetime, until: datetime) -> LeadBundle:
        """Fetch real leads for the reporting window."""

    @abstractmethod
    def probe(self) -> bool:
        """Verify the CRM connection."""
