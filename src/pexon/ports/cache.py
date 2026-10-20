"""Cache port."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class CachePort(ABC):
    """Small JSON cache."""

    @property
    @abstractmethod
    def provider(self) -> str:
        """Registered provider name."""

    @abstractmethod
    def get_json(self, key: str) -> Any | None:
        """Read a cached JSON value."""

    @abstractmethod
    def set_json(self, key: str, value: Any, ttl_seconds: int | None = None) -> None:
        """Write a cached JSON value."""

    @abstractmethod
    def probe(self) -> bool:
        """Verify cache reachability."""
