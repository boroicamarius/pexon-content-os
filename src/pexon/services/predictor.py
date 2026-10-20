"""Real model inference with a calibrated prior before enough data exists."""

from __future__ import annotations

import base64
import json
import logging
import pickle
from datetime import UTC, datetime
from typing import Any

from pexon.config.settings import Settings
from pexon.models.prediction import CalibrationCurve, Prediction, TargetCalibration
from pexon.models.weights import Weights
from pexon.ports.storage import StoragePort
from pexon.services import calibrator
from pexon.services.boosting import LocalGradientBoostingRegressor

logger = logging.getLogger(__name__)
_FEATURE_KEYS = (
    "seo",
    "geo",
    "aeo",
    "entity_coverage",
    "answer_first",
    "source_authority",
    "freshness",
)


class Predictor:
    """Champion model inference with bootstrap intervals and a documented prior."""

    def __init__(self, settings: Settings, storage: StoragePort) -> None:
        self._settings = settings
        self._storage = storage
        self._loaded_version: str | None = None
        self._model: Any = None
        self._calibration: TargetCalibration | None = None
        self._weights: Weights | None = None
        self._card: dict[str, Any] | None = None

    def _load(self) -> None:
        champion = self._storage.latest("weights", order_by="trained_at")
        if not champion:
            self._loaded_version = None
            self._model = None
            self._weights = None
            self._card = None
            return
        if self._loaded_version == champion["version"]:
            return
        self._weights = Weights(
            version=str(champion["version"]),
            values=champion.get("values_json") or {},
            intercept=float(champion.get("intercept", 0.0)),
            trained_at=datetime.fromisoformat(str(champion.get("trained_at"))),
            model_json=champion.get("model_json") or "",
            calibration_json=champion.get("calibration_json") or "",
            backend=str(champion.get("backend") or "pexon-gb"),
            row_count=int(champion.get("row_count") or 0),
            metrics=champion.get("metrics_json") or {},
            provider_config=champion.get("provider_config_json") or {},
        )
        self._model = self._deserialize(self._weights)
        self._calibration = self._parse_calibration(self._weights)
        cards = self._storage.find("model_cards", version=self._weights.version)
        self._card = cards[0] if cards else None
        self._loaded_version = self._weights.version

    def _deserialize(self, weights: Weights) -> dict[str, Any]:
        if weights.backend == "sklearn":
            blob = base64.b64decode(weights.model_json or "")
            return pickle.loads(blob)
        payload = weights.model_json or "{}"
        envelope = json.loads(payload) if isinstance(payload, str) else payload
        return {
            "clicks": LocalGradientBoostingRegressor.from_dict(envelope["clicks"]),
            "impressions": LocalGradientBoostingRegressor.from_dict(envelope["impressions"]),
        }

    @staticmethod
    def _parse_calibration(weights: Weights) -> TargetCalibration | None:
        if not weights.calibration_json:
            return None
        try:
            return TargetCalibration.model_validate_json(weights.calibration_json)
        except Exception:
            return None

    def predict(self, features: dict[str, float]) -> Prediction:
        """Predict both targets with calibrated bounds."""
        self._load()
        if self._weights is None or self._model is None:
            return self._prior(features)
        click_model = self._model["clicks"]
        impression_model = self._model["impressions"]
        click_names = getattr(click_model, "feature_names_in_", None) or getattr(
            click_model, "_pexon_feature_names", None
        )
        click_names = (
            list(click_names)
            if click_names is not None
            else list(getattr(click_model, "feature_names", []) or features)
        )
        impression_names = getattr(impression_model, "feature_names_in_", None) or getattr(
            impression_model, "_pexon_feature_names", None
        )
        impression_names = (
            list(impression_names)
            if impression_names is not None
            else list(getattr(impression_model, "feature_names", []) or features)
        )
        raw_clicks = float(click_model.predict([[features.get(n, 0.0) for n in click_names]])[0])
        raw_impressions = float(
            impression_model.predict([[features.get(n, 0.0) for n in impression_names]])[0]
        )
        clicks, c_low, c_high = self._bounds(raw_clicks, "clicks")
        impressions, i_low, i_high = self._bounds(raw_impressions, "impressions")
        return Prediction(
            expected_clicks=round(max(0.0, clicks), 2),
            expected_impressions=round(max(0.0, impressions), 2),
            expected_position=self._settings.expected_default_position,
            clicks_ci_low=round(max(0.0, c_low), 2),
            clicks_ci_high=round(max(0.0, c_high), 2),
            impressions_ci_low=round(max(0.0, i_low), 2),
            impressions_ci_high=round(max(0.0, i_high), 2),
            model_version=self._weights.version,
        )

    def _bounds(self, prediction: float, target: str) -> tuple[float, float, float]:
        if self._calibration is None:
            spread = self._settings.cold_start_ci_spread
            value = max(0.0, prediction)
            return value, value * (1 - spread), value * (1 + spread)
        curve: CalibrationCurve = getattr(self._calibration, target)
        seed = self._settings.random_seed + (0 if target == "clicks" else 1)
        return calibrator.interval(
            curve,
            prediction,
            lower_percentile=self._settings.ci_lower_percentile,
            upper_percentile=self._settings.ci_upper_percentile,
            iterations=self._settings.bootstrap_iterations,
            seed=seed,
        )

    def _prior(self, features: dict[str, float]) -> Prediction:
        quality = sum(features.get(k, 0.0) for k in _FEATURE_KEYS) / len(_FEATURE_KEYS)
        clicks = self._settings.baseline_clicks * (
            1.0 + self._settings.cold_start_click_multiplier * quality
        )
        impressions = self._settings.baseline_impressions * (
            1.0 + self._settings.cold_start_impression_multiplier * quality
        )
        spread = self._settings.cold_start_ci_spread
        return Prediction(
            expected_clicks=round(clicks, 2),
            expected_impressions=round(impressions, 2),
            expected_position=self._settings.expected_default_position,
            clicks_ci_low=round(clicks * (1 - spread), 2),
            clicks_ci_high=round(clicks * (1 + spread), 2),
            impressions_ci_low=round(impressions * (1 - spread), 2),
            impressions_ci_high=round(impressions * (1 + spread), 2),
            model_version="prior-v1",
            created_at=datetime.now(UTC),
        )

    def feature_importances(self) -> dict[str, float]:
        """Return the champion's importance weights for refinement."""
        self._load()
        return dict(self._weights.values) if self._weights else {}

    def champion_summary(self) -> dict[str, Any]:
        """Return provenance for CLI and logs."""
        self._load()
        if self._weights is None:
            return {"version": "prior-v1", "trained": False}
        return {
            "version": self._weights.version,
            "trained": True,
            "backend": self._weights.backend,
            "trained_at": self._weights.trained_at.isoformat(),
            "metrics": self._weights.metrics,
            "importances": self._weights.values,
            "provider_config": self._weights.provider_config,
            "model_card": {
                "known_limits": (self._card or {}).get("known_limits", ""),
                "row_count": (self._card or {}).get("row_count", self._weights.row_count),
                "metrics": (self._card or {}).get("metrics_json", self._weights.metrics),
            },
        }
