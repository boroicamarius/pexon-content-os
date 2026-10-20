"""Analytics port."""

from __future__ import annotations

from abc import ABC, abstractmethod

from pexon.models.performance import PerformanceBundle


class AnalyticsPort(ABC):
    """Measured search performance for an article."""

    @property
    @abstractmethod
    def provider(self) -> str:
        """Registered provider name."""

    @abstractmethod
    def fetch(
        self,
        article_id: str,
        *,
        window_days: int,
        page_url: str | None = None,
    ) -> PerformanceBundle:
        """Read real performance for one article."""

    @abstractmethod
    def probe(self) -> bool:
        """Make a cheap real read."""
