"""Champion-challenger learning with time-based evaluation and calibration."""

from __future__ import annotations

import base64
import json
import logging
import pickle
from datetime import UTC, datetime
from typing import Any

try:
    from sklearn.ensemble import GradientBoostingRegressor as SklearnGBR

    _HAS_SKLEARN = True
except ImportError:
    SklearnGBR = None  # type: ignore[assignment]
    _HAS_SKLEARN = False

from pexon.config.settings import Settings
from pexon.models.model_card import ModelCard
from pexon.models.prediction import TrainingReport
from pexon.models.weights import Weights
from pexon.ports.storage import StoragePort
from pexon.services import calibrator
from pexon.services.audit import AuditLog
from pexon.services.boosting import LocalGradientBoostingRegressor, mae, r2_score
from pexon.services.predictor import Predictor

logger = logging.getLogger(__name__)


class Learner:
    """Fits two real regressors and promotes only a beating challenger."""

    def __init__(self, settings: Settings, storage: StoragePort, audit: AuditLog) -> None:
        self._settings = settings
        self._storage = storage
        self._audit = audit

    def fit(self, run_id: str) -> TrainingReport:
        """Load measured pairs, train, evaluate, calibrate and version the champion."""
        rows = self._load_rows()
        if len(rows) < self._settings.min_training_rows:
            reason = f"insufficient rows: {len(rows)} < {self._settings.min_training_rows}"
            self._audit.emit(run_id, "learner_skipped", {"reason": reason, "rows": len(rows)})
            return TrainingReport(trained=False, reason=reason, version="")
        rows.sort(key=lambda row: row["created_at"])
        test_size = max(1, int(len(rows) * self._settings.train_test_split))
        train_rows, test_rows = rows[:-test_size], rows[-test_size:]
        if len(train_rows) < self._settings.min_training_rows:
            reason = f"training split too small: {len(train_rows)}"
            self._audit.emit(run_id, "learner_skipped", {"reason": reason})
            return TrainingReport(trained=False, reason=reason, version="")
        feature_names = sorted({key for row in rows for key in row["features"]})
        x_train = [
            [float(row["features"].get(name, 0.0)) for name in feature_names] for row in train_rows
        ]
        x_test = [
            [float(row["features"].get(name, 0.0)) for name in feature_names] for row in test_rows
        ]
        y_train_clicks = [row["clicks"] for row in train_rows]
        y_train_impressions = [row["impressions"] for row in train_rows]
        y_test_clicks = [row["clicks"] for row in test_rows]
        y_test_impressions = [row["impressions"] for row in test_rows]

        click_model = self._make_model(feature_names)
        impression_model = self._make_model(feature_names)
        self._fit(click_model, x_train, y_train_clicks)
        self._fit(impression_model, x_train, y_train_impressions)
        pred_clicks = self._predict(click_model, x_test)
        pred_impressions = self._predict(impression_model, x_test)
        new_mae_clicks = mae(y_test_clicks, pred_clicks)
        new_mae_impressions = mae(y_test_impressions, pred_impressions)

        champion = self._storage.latest("weights", order_by="trained_at")
        champion_mae_clicks = champion_mae_impressions = float("inf")
        champion_version = ""
        if champion:
            champion_version = str(champion.get("version", ""))
            champion_mae_clicks, champion_mae_impressions = self._champion_mae(
                test_rows, feature_names
            )
        beats = (
            new_mae_clicks + self._settings.champion_min_delta < champion_mae_clicks
            and new_mae_impressions + self._settings.champion_min_delta < champion_mae_impressions
        )
        if champion and not beats:
            reason = (
                "challenger did not beat champion: "
                f"clicks {new_mae_clicks:.2f} vs {champion_mae_clicks:.2f}; "
                f"impressions {new_mae_impressions:.2f} vs {champion_mae_impressions:.2f}"
            )
            self._audit.emit(
                run_id,
                "learner_rejected",
                {"reason": reason, "champion": champion_version, "rows": len(rows)},
            )
            return TrainingReport(
                trained=False, reason=reason, version=champion_version, row_count=len(rows)
            )

        calibration = calibrator.fit(
            pred_clicks, y_test_clicks, pred_impressions, y_test_impressions
        )
        importances = self._importances(click_model, impression_model, feature_names)
        metrics = {
            "mae_clicks": round(new_mae_clicks, 4),
            "mae_impressions": round(new_mae_impressions, 4),
            "r2_clicks": round(r2_score(y_test_clicks, pred_clicks), 4),
            "r2_impressions": round(r2_score(y_test_impressions, pred_impressions), 4),
            "test_rows": float(len(test_rows)),
            "train_rows": float(len(train_rows)),
        }
        version = self._next_version()
        backend = "sklearn" if _HAS_SKLEARN else "pexon-gb"
        model_json = self._serialize_models(click_model, impression_model, backend)
        weights = Weights(
            version=version,
            values=importances,
            intercept=0.0 if _HAS_SKLEARN else float(click_model.base),
            trained_at=datetime.now(UTC),
            model_json=model_json,
            calibration_json=calibration.model_dump_json(),
            backend=backend,
            row_count=len(rows),
            metrics=metrics,
            provider_config=self._settings.provider_config,
        )
        known_limits = (
            "Trained on a small, time-ordered local corpus. Competitor features are "
            "LLM-assigned and therefore noisy. Isotonic intervals assume exchangeable "
            "residuals; drift is detected but never auto-corrected. Clicks and impressions "
            "are only as complete as the selected analytics adapter."
        )
        card = ModelCard(
            version=version,
            trained_at=weights.trained_at,
            features=tuple(feature_names),
            metrics=metrics,
            known_limits=known_limits,
            row_count=len(rows),
            provider_config=self._settings.provider_config,
        )
        weight_row = {
            "id": f"weights-{version}",
            "version": version,
            "values_json": importances,
            "intercept": float(click_model.base if not _HAS_SKLEARN else 0.0),
            "trained_at": weights.trained_at.isoformat(),
            "model_json": model_json,
            "calibration_json": calibration.model_dump_json(),
            "backend": backend,
            "metrics_json": metrics,
            "row_count": len(rows),
            "provider_config_json": self._settings.provider_config,
        }
        self._storage.write("weights", weight_row)
        card_row = {
            "id": f"card-{version}",
            "version": version,
            "features_json": list(card.features),
            "metrics_json": metrics,
            "known_limits": known_limits,
            "row_count": len(rows),
            "provider_config_json": self._settings.provider_config,
            "trained_at": weights.trained_at.isoformat(),
            "created_at": weights.trained_at.isoformat(),
        }
        self._storage.write("model_cards", card_row)
        self._audit.emit(
            run_id,
            "learner_promoted",
            {
                "version": version,
                "metrics": metrics,
                "champion": champion_version,
                "provider_config": self._settings.provider_config,
            },
        )
        return TrainingReport(
            trained=True,
            reason="champion promoted",
            version=version,
            metrics=metrics,
            row_count=len(rows),
        )

    def _load_rows(self) -> list[dict[str, Any]]:
        performance = self._storage.find("performance")
        features = self._storage.find("features")
        articles = {row["id"]: row for row in self._storage.find("articles")}
        latest_perf: dict[str, dict[str, Any]] = {}
        for row in performance:
            current = latest_perf.get(row["article_id"])
            if current is None or str(row.get("measured_at", "")) > str(
                current.get("measured_at", "")
            ):
                latest_perf[row["article_id"]] = row
        latest_features: dict[str, dict[str, Any]] = {}
        for row in features:
            article = row["article_id"]
            current = latest_features.get(article)
            if current is None or str(row.get("created_at", "")) > str(
                current.get("created_at", "")
            ):
                latest_features[article] = row
        rows: list[dict[str, Any]] = []
        for article_id, perf in latest_perf.items():
            feature_row = latest_features.get(article_id)
            article = articles.get(article_id)
            if not feature_row or not article:
                continue
            values = feature_row.get("features_json") or {}
            if not isinstance(values, dict):
                continue
            rows.append(
                {
                    "article_id": article_id,
                    "created_at": str(article.get("created_at", "")),
                    "features": {
                        k: float(v) for k, v in values.items() if isinstance(v, (int, float))
                    },
                    "clicks": float(perf.get("clicks", 0)),
                    "impressions": float(perf.get("impressions", 0)),
                }
            )
        return rows

    def _make_model(self, feature_names: list[str]) -> Any:
        if _HAS_SKLEARN:
            model = SklearnGBR(
                n_estimators=self._settings.gb_n_estimators,
                learning_rate=self._settings.gb_learning_rate,
                max_depth=self._settings.gb_max_depth,
                min_samples_leaf=self._settings.gb_min_samples_leaf,
                subsample=self._settings.gb_subsample,
                random_state=self._settings.random_seed,
            )
            model._pexon_feature_names = feature_names  # type: ignore[attr-defined]
            return model
        return LocalGradientBoostingRegressor(
            n_estimators=self._settings.gb_n_estimators,
            learning_rate=self._settings.gb_learning_rate,
            max_depth=self._settings.gb_max_depth,
            min_samples_leaf=self._settings.gb_min_samples_leaf,
            subsample=self._settings.gb_subsample,
            random_state=self._settings.random_seed,
            feature_names=feature_names,
        )

    @staticmethod
    def _fit(model: Any, x_train: list[list[float]], y_train: list[float]) -> None:
        model.fit(x_train, y_train)

    @staticmethod
    def _predict(model: Any, rows: list[list[float]]) -> list[float]:
        return [float(value) for value in model.predict(rows)]

    def _champion_mae(
        self, test_rows: list[dict[str, Any]], feature_names: list[str]
    ) -> tuple[float, float]:
        predictor = Predictor(self._settings, self._storage)
        predicted_clicks: list[float] = []
        predicted_impressions: list[float] = []
        for row in test_rows:
            prediction = predictor.predict(row["features"])
            predicted_clicks.append(prediction.expected_clicks)
            predicted_impressions.append(prediction.expected_impressions)
        return (
            mae([row["clicks"] for row in test_rows], predicted_clicks),
            mae([row["impressions"] for row in test_rows], predicted_impressions),
        )

    def _serialize_models(self, click_model: Any, impression_model: Any, backend: str) -> str:
        if backend == "sklearn":
            return base64.b64encode(
                pickle.dumps({"clicks": click_model, "impressions": impression_model})
            ).decode("ascii")
        return json.dumps(
            {
                "clicks": click_model.to_dict(),
                "impressions": impression_model.to_dict(),
            },
            ensure_ascii=False,
        )

    def _importances(
        self, click_model: Any, impression_model: Any, feature_names: list[str]
    ) -> dict[str, float]:
        if _HAS_SKLEARN:
            click_values = list(
                getattr(click_model, "feature_importances_", [0.0] * len(feature_names))
            )
            impression_values = list(
                getattr(impression_model, "feature_importances_", [0.0] * len(feature_names))
            )
        else:
            click_values = [click_model.importances_.get(name, 0.0) for name in feature_names]
            impression_values = [
                impression_model.importances_.get(name, 0.0) for name in feature_names
            ]
        combined = [(a + b) / 2 for a, b in zip(click_values, impression_values, strict=False)]
        total = sum(combined) or 1.0
        return {
            name: round(value / total, 6)
            for name, value in zip(feature_names, combined, strict=False)
        }

    def _next_version(self) -> str:
        cards = self._storage.find("model_cards")
        highest = 0
        for card in cards:
            version = str(card.get("version", "v0"))
            if version.startswith("v") and version[1:].isdigit():
                highest = max(highest, int(version[1:]))
        return f"v{highest + 1}"
