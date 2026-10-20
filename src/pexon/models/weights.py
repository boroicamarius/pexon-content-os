"""Learned weights value objects."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import Field

from pexon.models.base import FrozenModel


class Weights(FrozenModel):
    """Versioned champion model, calibration and importances."""

    version: str
    values: dict[str, float]
    intercept: float
    trained_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    model_json: str = ""
    calibration_json: str = ""
    backend: str = "pexon-gb"
    row_count: int = 0
    metrics: dict[str, float] = Field(default_factory=dict)
    provider_config: dict[str, object] = Field(default_factory=dict)
