"""Prediction and calibration value objects."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import Field

from pexon.models.base import FrozenModel


class Prediction(FrozenModel):
    """Expected performance with calibrated uncertainty."""

    expected_clicks: float
    expected_impressions: float
    expected_position: float
    clicks_ci_low: float
    clicks_ci_high: float
    impressions_ci_low: float
    impressions_ci_high: float
    model_version: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class CalibrationCurve(FrozenModel):
    """Isotonic map plus residual pool for bootstrap intervals."""

    x: tuple[float, ...]
    y: tuple[float, ...]
    residuals: tuple[float, ...]
    residual_scale: float = 1.0


class TargetCalibration(FrozenModel):
    """Calibration for both business targets."""

    clicks: CalibrationCurve
    impressions: CalibrationCurve


class TrainingReport(FrozenModel):
    """Outcome of one champion-challenger training attempt."""

    trained: bool
    reason: str
    version: str
    metrics: dict[str, float] = Field(default_factory=dict)
    row_count: int = 0


class Proposal(FrozenModel):
    """A measured-error-driven prompt adjustment."""

    diagnosis_de: str
    adjustment_de: str
    target_prompt: str
    expected_effect_de: str


class PromptMutation(FrozenModel):
    """A complete replacement prompt template."""

    name: str
    template_de: str
    rationale_de: str
