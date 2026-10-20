"""Isotonic calibration and bootstrap confidence intervals."""

from __future__ import annotations

import random

from pexon.models.prediction import CalibrationCurve, TargetCalibration


def _pava(xs: list[float], ys: list[float]) -> tuple[list[float], list[float]]:
    blocks: list[list[float]] = []  # [sum_y, count, x]
    for x, y in zip(xs, ys, strict=False):
        blocks.append([y, 1.0, x])
        while len(blocks) > 1 and blocks[-2][0] / blocks[-2][1] > blocks[-1][0] / blocks[-1][1]:
            last = blocks.pop()
            previous = blocks.pop()
            blocks.append([previous[0] + last[0], previous[1] + last[1], last[2]])
    output_x: list[float] = []
    output_y: list[float] = []
    for total, count, x in blocks:
        output_x.append(x)
        output_y.append(total / count)
    return output_x, output_y


def fit_curve(predictions: list[float], actuals: list[float]) -> CalibrationCurve:
    """Fit an isotonic curve and retain residuals for bootstrap sampling."""
    pairs = sorted(zip(predictions, actuals, strict=False), key=lambda pair: pair[0])
    if not pairs:
        return CalibrationCurve(x=(0.0,), y=(0.0,), residuals=(0.0,))
    xs = [max(0.0, pair[0]) for pair in pairs]
    ys = [pair[1] for pair in pairs]
    curve_x, curve_y = _pava(xs, ys)
    calibrated = [
        apply_curve(CalibrationCurve(x=tuple(curve_x), y=tuple(curve_y), residuals=(0.0,)), x)
        for x in xs
    ]
    residuals = [actual - predicted for actual, predicted in zip(ys, calibrated, strict=False)]
    scale = (sum(abs(r) for r in residuals) / len(residuals)) or 1.0
    return CalibrationCurve(
        x=tuple(curve_x),
        y=tuple(curve_y),
        residuals=tuple(residuals),
        residual_scale=scale,
    )


def apply_curve(curve: CalibrationCurve, value: float) -> float:
    """Piecewise-linear interpolation over the isotonic curve."""
    if not curve.x:
        return max(0.0, value)
    if value <= curve.x[0]:
        return max(0.0, curve.y[0])
    if value >= curve.x[-1]:
        return max(0.0, curve.y[-1])
    for index in range(1, len(curve.x)):
        if value <= curve.x[index]:
            left_x, right_x = curve.x[index - 1], curve.x[index]
            left_y, right_y = curve.y[index - 1], curve.y[index]
            span = right_x - left_x
            if span <= 0:
                return max(0.0, right_y)
            ratio = (value - left_x) / span
            return max(0.0, left_y + ratio * (right_y - left_y))
    return max(0.0, curve.y[-1])


def fit(
    predicted_clicks: list[float],
    actual_clicks: list[float],
    predicted_impressions: list[float],
    actual_impressions: list[float],
) -> TargetCalibration:
    """Fit independent calibrators for both targets."""
    return TargetCalibration(
        clicks=fit_curve(predicted_clicks, actual_clicks),
        impressions=fit_curve(predicted_impressions, actual_impressions),
    )


def interval(
    curve: CalibrationCurve,
    prediction: float,
    *,
    lower_percentile: float,
    upper_percentile: float,
    iterations: int,
    seed: int,
) -> tuple[float, float, float]:
    """Return calibrated mean and bootstrap percentile bounds."""
    mean = apply_curve(curve, prediction)
    if not curve.residuals or iterations <= 0:
        return mean, max(0.0, mean), max(0.0, mean)
    rng = random.Random(seed)
    draws = [max(0.0, mean + rng.choice(curve.residuals)) for _ in range(iterations)]
    draws.sort()
    low_index = min(len(draws) - 1, max(0, int(lower_percentile * len(draws))))
    high_index = min(len(draws) - 1, max(0, int(upper_percentile * len(draws)) - 1))
    return mean, draws[low_index], draws[high_index]
