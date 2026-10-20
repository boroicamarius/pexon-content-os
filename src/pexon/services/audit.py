"""Append-only audit trail."""

from __future__ import annotations

import logging
from typing import Any

from pexon.models.events import Event
from pexon.ports.storage import StoragePort

logger = logging.getLogger(__name__)


class AuditLog:
    """Writes the events table; every loop and fallback is visible."""

    def __init__(self, storage: StoragePort) -> None:
        self._storage = storage

    def emit(
        self,
        run_id: str,
        kind: str,
        payload: dict[str, Any] | None = None,
        article_id: str | None = None,
    ) -> Event:
        """Persist one event."""
        event = Event(run_id=run_id, article_id=article_id, kind=kind, payload=payload or {})
        row = event.model_dump(mode="json")
        row["payload_json"] = row.pop("payload")
        self._storage.write("events", row)
        logger.info("event %s", kind, extra={"extra_fields": {"kind": kind, "run_id": run_id}})
        return event
