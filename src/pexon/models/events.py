"""Append-only audit event value objects."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from pydantic import Field

from pexon.models.base import FrozenModel


class Event(FrozenModel):
    """One append-only audit record."""

    ts: datetime = Field(default_factory=lambda: datetime.now(UTC))
    run_id: str
    article_id: str | None = None
    kind: str
    payload: dict[str, object] = Field(default_factory=dict)
    id: str = Field(default_factory=lambda: uuid4().hex)


class ProviderConfig(FrozenModel):
    """Safe provider provenance for a run or model card."""

    values: dict[str, object]


class ProviderProbe(FrozenModel):
    """Result of a real adapter probe."""

    port: str
    provider: str
    ok: bool
    detail: str = ""
