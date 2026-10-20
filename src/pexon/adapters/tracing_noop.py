"""No-op tracing adapter."""

from __future__ import annotations

from contextlib import AbstractContextManager, nullcontext

from pexon.config.settings import Settings
from pexon.ports.tracing import TracingPort

AVAILABLE = True
UNAVAILABLE_REASON = ""


class NoOpTracing(TracingPort):
    """Disables tracing without changing service code."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    @property
    def provider(self) -> str:
        return "none"

    def span(
        self, name: str, *, run_id: str, inputs: dict[str, object] | None = None
    ) -> AbstractContextManager[None]:
        """Return a no-op context manager."""
        return nullcontext()

    def probe(self) -> bool:
        """Always available."""
        return True
