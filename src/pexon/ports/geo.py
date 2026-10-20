"""Generative-engine visibility port."""
from __future__ import annotations

from abc import ABC, abstractmethod

from pexon.models.geo import GeoReport


class GeoPort(ABC):
    """Measure whether real AI answer engines mention or cite the brand."""

    @property
    @abstractmethod
    def provider(self) -> str:
        """Registered provider name."""

    @abstractmethod
    def measure(self, queries: list[str], *, brand: str, domain: str,
                topic_id: str, article_id: str | None = None) -> GeoReport:
        """Run the real engine queries and return visibility evidence."""

    @abstractmethod
    def probe(self) -> bool:
        """Verify the engine endpoint."""
