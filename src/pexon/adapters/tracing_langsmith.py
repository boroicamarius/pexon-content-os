"""Opt-in LangSmith tracing adapter."""

from __future__ import annotations

from contextlib import AbstractContextManager
from typing import Any

from pexon.config.settings import Settings
from pexon.ports.errors import ProviderError
from pexon.ports.tracing import TracingPort

try:
    from langsmith import Client
    from langsmith.run_trees import RunTree

    _HAS_LANGSMITH = True
except ImportError:
    Client = None  # type: ignore[assignment,misc]
    RunTree = None  # type: ignore[assignment,misc]
    _HAS_LANGSMITH = False

AVAILABLE = _HAS_LANGSMITH
UNAVAILABLE_REASON = "install langsmith"


class _RunSpan:
    def __init__(self, run: Any, client: Any) -> None:
        self._run = run
        self._client = client

    def __enter__(self) -> None:
        return None

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        try:
            self._run.end(error=str(exc) if exc else None)
            self._run.post(exclude_child_runs=False)
        except Exception:
            pass
        return None


class LangSmithTracing(TracingPort):
    """Creates one root run per graph span and posts it to LangSmith."""

    def __init__(self, settings: Settings) -> None:
        self._project = settings.langsmith_project
        self._client = Client() if _HAS_LANGSMITH else None

    @property
    def provider(self) -> str:
        return "langsmith"

    def span(
        self, name: str, *, run_id: str, inputs: dict[str, object] | None = None
    ) -> AbstractContextManager[None]:
        """Open and post a LangSmith run tree."""
        if self._client is None:
            raise ProviderError(UNAVAILABLE_REASON)
        run = RunTree(
            name=name,
            run_type="chain",
            inputs=inputs or {},
            project_name=self._project,
            ls_client=self._client,
        )
        return _RunSpan(run, self._client)

    def probe(self) -> bool:
        """Read the configured project through the real client."""
        if self._client is None:
            raise ProviderError(UNAVAILABLE_REASON)
        self._client.list_projects(limit=1)
        return True
