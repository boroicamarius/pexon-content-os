"""Tracing port."""

from __future__ import annotations

from abc import ABC, abstractmethod
from contextlib import AbstractContextManager


class TracingPort(ABC):
    """Optional trace sink."""

    @property
    @abstractmethod
    def provider(self) -> str:
        """Registered provider name."""

    @abstractmethod
    def span(
        self,
        name: str,
        *,
        run_id: str,
        inputs: dict[str, object] | None = None,
    ) -> AbstractContextManager[None]:
        """Open a named trace span."""

    @abstractmethod
    def probe(self) -> bool:
        """Verify tracing credentials without creating a publication."""
