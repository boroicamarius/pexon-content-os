"""Keyword-demand port."""
from __future__ import annotations

from abc import ABC, abstractmethod

from pexon.models.portfolio import KeywordDemand


class KeywordPort(ABC):
    """Provide real search demand for portfolio planning."""

    @property
    @abstractmethod
    def provider(self) -> str:
        """Registered provider name."""

    @abstractmethod
    def demand(self, seeds: list[str], limit: int) -> list[KeywordDemand]:
        """Return keyword demand for the seeds."""

    @abstractmethod
    def probe(self) -> bool:
        """Verify the demand source."""
