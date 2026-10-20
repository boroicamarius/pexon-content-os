"""Embeddings port."""

from __future__ import annotations

from abc import ABC, abstractmethod


class EmbeddingsPort(ABC):
    """Dense or lexical embeddings with a stable shape."""

    @property
    @abstractmethod
    def provider(self) -> str:
        """Registered provider name."""

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed texts."""

    @abstractmethod
    def probe(self) -> bool:
        """Make a cheap real embedding call."""
