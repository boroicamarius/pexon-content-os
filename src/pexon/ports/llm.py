"""LLM port."""

from __future__ import annotations

from abc import ABC, abstractmethod

from pydantic import BaseModel


class LLMResult(BaseModel):
    """Provider response plus accounting metadata."""

    text: str
    provider: str
    model: str
    tokens_in: int = 0
    tokens_out: int = 0
    finish_reason: str = ""


class LLMPort(ABC):
    """Text generation with a provider-neutral interface."""

    @property
    @abstractmethod
    def provider(self) -> str:
        """Registered provider name."""

    @property
    @abstractmethod
    def model(self) -> str:
        """Active model id."""

    @property
    @abstractmethod
    def base_url(self) -> str:
        """Provider endpoint."""

    @abstractmethod
    def generate(
        self,
        system: str,
        prompt: str,
        *,
        json_mode: bool = False,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LLMResult:
        """Generate text with a real provider call."""

    @abstractmethod
    def probe(self) -> bool:
        """Make a cheap real call to verify reachability."""
