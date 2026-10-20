"""Search port."""

from __future__ import annotations

from abc import ABC, abstractmethod

from pexon.models.research import Source


class SearchPort(ABC):
    """Web search returning source candidates."""

    @property
    @abstractmethod
    def provider(self) -> str:
        """Registered provider name."""

    @abstractmethod
    def search(self, query: str, max_results: int) -> list[Source]:
        """Search the public web."""

    @abstractmethod
    def probe(self) -> bool:
        """Make a cheap real search."""
