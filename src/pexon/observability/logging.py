"""Structured JSON logging with a per-run trace id."""

from __future__ import annotations

import json
import logging
import sys
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

_TRACE_ID: ContextVar[str] = ContextVar("pexon_trace_id", default="-")


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "trace_id": _TRACE_ID.get(),
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        for key, value in getattr(record, "extra_fields", {}).items():
            payload[key] = value
        return json.dumps(payload, ensure_ascii=False, default=str)


class _TextFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return (
            f"{datetime.now(UTC).strftime('%H:%M:%S')} "
            f"[{record.levelname.lower()}] [{_TRACE_ID.get()[:8]}] {record.getMessage()}"
        )


def configure_logging(level: str = "INFO", fmt: str = "json") -> None:
    """Install one stderr handler with trace context."""
    root = logging.getLogger()
    root.handlers.clear()
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(_JsonFormatter() if fmt == "json" else _TextFormatter())
    root.addHandler(handler)
    root.setLevel(level.upper())


def set_trace_id(trace_id: str) -> None:
    """Bind the current run's trace id."""
    _TRACE_ID.set(trace_id)


def get_trace_id() -> str:
    """Read the current trace id."""
    return _TRACE_ID.get()


def log_extra(**fields: Any) -> dict[str, Any]:
    """Convenience payload for logging's extra field."""
    return {"extra_fields": fields}
