"""PSI feature drift and KS target drift; detection only, never auto-refit."""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta
from typing import Any

from pexon.config.settings import Settings
from pexon.ports.storage import StoragePort
from pexon.services.audit import AuditLog


class DriftMonitor:
    """Detects distribution shifts against the most recent training window."""

    def __init__(self, settings: Settings, storage: StoragePort, audit: AuditLog) -> None:
        self._settings = settings
        self._storage = storage
        self._audit = audit

    def check(self, run_id: str) -> dict[str, Any]:
        """Compute PSI for features and KS for targets, then log one event."""
        feature_rows = self._feature_rows()
        performance = self._performance_rows()
        if (
            len(feature_rows) < self._settings.drift_min_rows
            or len(performance) < self._settings.drift_min_rows
        ):
            self._audit.emit(
                run_id,
                "drift_skipped",
                {"features": len(feature_rows), "performance": len(performance)},
            )
            return {"checked": False, "reason": "insufficient rows"}
        cutoff = datetime.now(UTC) - timedelta(days=self._settings.drift_window_days)
        reference = [row for row in feature_rows if row["ts"] < cutoff]
        current = [row for row in feature_rows if row["ts"] >= cutoff]
        if len(reference) < self._settings.drift_min_rows or not current:
            self._audit.emit(
                run_id, "drift_skipped", {"reference": len(reference), "current": len(current)}
            )
            return {"checked": False, "reason": "no current or reference window"}
        feature_keys = sorted({key for row in reference for key in row["values"]})
        psi_values = {
            key: round(
                psi(
                    [row["values"].get(key, 0.0) for row in reference],
                    [row["values"].get(key, 0.0) for row in current],
                    self._settings.drift_bins,
                    self._settings.drift_epsilon,
                ),
                4,
            )
            for key in feature_keys
        }
        ref_perf = [row for row in performance if row["ts"] < cutoff]
        cur_perf = [row for row in performance if row["ts"] >= cutoff]
        ref_clicks = [float(row["clicks"]) for row in ref_perf]
        cur_clicks = [float(row["clicks"]) for row in cur_perf]
        ref_impressions = [float(row["impressions"]) for row in ref_perf]
        cur_impressions = [float(row["impressions"]) for row in cur_perf]
        ks_clicks = ks(ref_clicks, cur_clicks)
        ks_impressions = ks(ref_impressions, cur_impressions)
        drifted_features = [
            k for k, v in psi_values.items() if v > self._settings.drift_psi_threshold
        ]
        target_drift = (
            ks_clicks > self._settings.drift_ks_threshold
            or ks_impressions > self._settings.drift_ks_threshold
        )
        report = {
            "checked": True,
            "psi": psi_values,
            "ks_clicks": round(ks_clicks, 4),
            "ks_impressions": round(ks_impressions, 4),
            "drifted_features": drifted_features,
            "target_drift": target_drift,
            "window_days": self._settings.drift_window_days,
        }
        self._audit.emit(run_id, "drift_checked", report)
        if drifted_features or target_drift:
            self._audit.emit(run_id, "drift_detected", report)
        return report

    def _feature_rows(self) -> list[dict[str, Any]]:
        articles = {row["id"]: row for row in self._storage.find("articles")}
        rows: list[dict[str, Any]] = []
        for row in self._storage.find("features"):
            article = articles.get(row["article_id"])
            if not article:
                continue
            values = row.get("features_json") or {}
            if not isinstance(values, dict):
                continue
            rows.append(
                {
                    "ts": _parse(row["created_at"]),
                    "values": {
                        k: float(v) for k, v in values.items() if isinstance(v, (int, float))
                    },
                }
            )
        return rows

    def _performance_rows(self) -> list[dict[str, Any]]:
        return [
            {
                "ts": _parse(row["measured_at"]),
                "clicks": float(row["clicks"]),
                "impressions": float(row["impressions"]),
            }
            for row in self._storage.find("performance")
        ]


def _parse(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    except ValueError:
        return datetime.now(UTC)


def psi(
    reference: list[float], current: list[float], bins: int, epsilon: float = 0.000001
) -> float:
    """Population Stability Index over reference quantile bins."""
    if not reference or not current:
        return 0.0
    ordered = sorted(reference)
    edges = [_quantile(ordered, i / bins) for i in range(bins + 1)]
    ref_counts = _bucket(reference, edges, bins)
    cur_counts = _bucket(current, edges, bins)
    total_ref = max(sum(ref_counts), 1)
    total_cur = max(sum(cur_counts), 1)
    value = 0.0
    for ref_count, cur_count in zip(ref_counts, cur_counts, strict=False):
        ref_share = max(ref_count / total_ref, epsilon)
        cur_share = max(cur_count / total_cur, epsilon)
        value += (cur_share - ref_share) * math.log(cur_share / ref_share)
    return max(0.0, value)


def _bucket(values: list[float], edges: list[float], bins: int) -> list[int]:
    counts = [0] * bins
    for value in values:
        index = bins - 1
        for candidate in range(bins):
            if value <= edges[candidate + 1]:
                index = candidate
                break
        counts[index] += 1
    return counts


def _quantile(ordered: list[float], fraction: float) -> float:
    if not ordered:
        return 0.0
    position = min(len(ordered) - 1, max(0, int(round(fraction * (len(ordered) - 1)))))
    return ordered[position]


def ks(reference: list[float], current: list[float]) -> float:
    """Two-sample Kolmogorov-Smirnov statistic."""
    if not reference or not current:
        return 0.0
    combined = sorted(set(reference + current))
    max_gap = 0.0
    for point in combined:
        ref_cdf = sum(1 for value in reference if value <= point) / len(reference)
        cur_cdf = sum(1 for value in current if value <= point) / len(current)
        max_gap = max(max_gap, abs(ref_cdf - cur_cdf))
    return max_gap
