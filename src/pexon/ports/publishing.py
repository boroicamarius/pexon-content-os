"""Publishing port."""
from __future__ import annotations

from abc import ABC, abstractmethod

from pexon.models.publishing import PublishRequest, PublishResult


class PublishingPort(ABC):
    """Deliver a finished article to a real publishing target."""

    @property
    @abstractmethod
    def provider(self) -> str:
        """Registered provider name."""

    @abstractmethod
    def publish(self, request: PublishRequest) -> PublishResult:
        """Publish or update one article."""

    @abstractmethod
    def probe(self) -> bool:
        """Verify credentials and endpoint."""
