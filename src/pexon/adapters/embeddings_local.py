"""Local embeddings: sentence-transformers when installed, hashed n-grams otherwise."""

from __future__ import annotations

import hashlib
import importlib.util
import math
import re

from pexon.config.settings import Settings
from pexon.ports.embeddings import EmbeddingsPort
from pexon.ports.errors import ProviderError

AVAILABLE = True
UNAVAILABLE_REASON = ""
_HAS_SENTENCE_TRANSFORMERS = importlib.util.find_spec("sentence_transformers") is not None
_TOKEN = re.compile(r"[A-Za-zÄÖÜäöüß0-9]+")


class LocalEmbeddings(EmbeddingsPort):
    """Runs entirely on the host; no API key and no network required."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._model = None
        if _HAS_SENTENCE_TRANSFORMERS:
            try:
                from sentence_transformers import SentenceTransformer

                self._model = SentenceTransformer(settings.embeddings_local_model)
            except Exception:
                self._model = None
        self._dim = settings.embeddings_local_dim

    @property
    def provider(self) -> str:
        return "local"

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed with the loaded model or deterministic multilingual character n-grams."""
        if not texts:
            return []
        if self._model is not None:
            try:
                vectors = self._model.encode(texts, normalize_embeddings=True)
                return [list(map(float, vec)) for vec in vectors]
            except Exception as exc:
                raise ProviderError(f"local sentence-transformers failed: {exc}") from exc
        return [self._hash_embedding(text) for text in texts]

    def _hash_embedding(self, text: str) -> list[float]:
        vector = [0.0] * self._dim
        tokens = [t.lower() for t in _TOKEN.findall(text)]
        grams: list[str] = []
        for token in tokens:
            padded = f"_{token}_"
            for n in (3, 4, 5):
                grams.extend(padded[i : i + n] for i in range(max(0, len(padded) - n + 1)))
        for gram in grams:
            digest = hashlib.blake2b(gram.encode("utf-8"), digest_size=8).digest()
            raw = int.from_bytes(digest, "big")
            index = raw % self._dim
            sign = 1.0 if (raw >> 63) & 1 else -1.0
            vector[index] += sign
        norm = math.sqrt(sum(v * v for v in vector)) or 1.0
        return [v / norm for v in vector]

    def probe(self) -> bool:
        """Embed one token-sized string."""
        return len(self.embed(["Pexon Governance"])[0]) > 0
