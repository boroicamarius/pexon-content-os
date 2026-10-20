"""Fetch port."""

from __future__ import annotations

from abc import ABC, abstractmethod

from pexon.models.research import FetchedPage


class FetchPort(ABC):
    """Fetch and extract a public page."""

    @property
    @abstractmethod
    def provider(self) -> str:
        """Registered provider name."""

    @abstractmethod
    def fetch(self, url: str) -> FetchedPage:
        """Fetch a URL and return readable text."""

    @abstractmethod
    def probe(self) -> bool:
        """Make a cheap real fetch."""
