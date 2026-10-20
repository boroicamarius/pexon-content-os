"""Model card value objects."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import Field

from pexon.models.base import FrozenModel


class ModelCard(FrozenModel):
    """Auditable model card including provider provenance."""

    version: str
    trained_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    features: tuple[str, ...]
    metrics: dict[str, float]
    known_limits: str
    row_count: int
    provider_config: dict[str, object]
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
