"""OpenAI-protocol embeddings adapter."""

from __future__ import annotations

from pexon.config.settings import Settings
from pexon.ports.embeddings import EmbeddingsPort
from pexon.ports.errors import ProviderError

try:
    from openai import OpenAI

    _HAS_OPENAI = True
except ImportError:
    OpenAI = None  # type: ignore[assignment,misc]
    _HAS_OPENAI = False

AVAILABLE = _HAS_OPENAI
UNAVAILABLE_REASON = "install openai"


class OpenAICompatibleEmbeddings(EmbeddingsPort):
    """Any endpoint exposing /embeddings with the OpenAI schema."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._model = settings.embeddings_model
        self._base_url = settings.effective_embeddings_base_url.rstrip("/")
        self._client = (
            OpenAI(
                base_url=self._base_url,
                api_key=settings.effective_embeddings_api_key or "not-needed",
                timeout=settings.embeddings_timeout_seconds,
            )
            if _HAS_OPENAI
            else None
        )

    @property
    def provider(self) -> str:
        return "openai-compatible"

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed texts in one real request."""
        if self._client is None:
            raise ProviderError(UNAVAILABLE_REASON)
        try:
            response = self._client.embeddings.create(model=self._model, input=texts)
        except Exception as exc:
            raise ProviderError(f"embeddings call failed: {exc}") from exc
        return [list(item.embedding) for item in response.data]

    def probe(self) -> bool:
        """Embed one token-sized string."""
        return len(self.embed(["Pexon"])[0]) > 0
