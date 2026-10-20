"""Dependency-free gradient boosted regression trees used when sklearn is absent."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Any


@dataclass
class _Node:
    value: float
    feature: int | None = None
    threshold: float | None = None
    left: _Node | None = None
    right: _Node | None = None


@dataclass
class LocalGradientBoostingRegressor:
    """Real gradient boosting with regression trees and deterministic subsampling."""

    n_estimators: int
    learning_rate: float
    max_depth: int
    min_samples_leaf: int
    subsample: float
    random_state: int
    feature_names: list[str] = field(default_factory=list)
    trees: list[_Node] = field(default_factory=list)
    base: float = 0.0
    importances_: dict[str, float] = field(default_factory=dict)
    _rng: random.Random = field(default_factory=lambda: random.Random(42), repr=False)

    def fit(self, X: list[list[float]], y: list[float]) -> LocalGradientBoostingRegressor:
        """Fit boosted trees to numeric rows."""
        if not X or len(X) != len(y):
            raise ValueError("X and y must be non-empty and aligned")
        self.base = sum(y) / len(y)
        current = [self.base] * len(y)
        self.trees = []
        gains = [0.0] * len(X[0])
        self._rng = random.Random(self.random_state)
        indices = list(range(len(y)))
        for _ in range(self.n_estimators):
            residuals = [y[i] - current[i] for i in range(len(y))]
            sample = (
                indices
                if self.subsample >= 1.0
                else [i for i in indices if self._rng.random() < self.subsample]
            )
            if len(sample) < self.min_samples_leaf * 2:
                sample = indices
            tree = self._build(X, residuals, sample, depth=0, gains=gains)
            self.trees.append(tree)
            for i in indices:
                current[i] += self.learning_rate * self._predict_tree(tree, X[i])
        total = sum(gains) or 1.0
        self.importances_ = {name: gains[i] / total for i, name in enumerate(self.feature_names)}
        return self

    def _build(
        self,
        X: list[list[float]],
        y: list[float],
        indices: list[int],
        *,
        depth: int,
        gains: list[float],
    ) -> _Node:
        node = _Node(value=sum(y[i] for i in indices) / len(indices))
        if depth >= self.max_depth or len(indices) < self.min_samples_leaf * 2:
            return node
        best_gain, best_feature, best_threshold = 0.0, None, None
        parent_sse = self._sse(y, indices)
        for feature in range(len(X[0])):
            values = sorted({X[i][feature] for i in indices})
            if len(values) < 2:
                continue
            candidates = self._candidates(values)
            for threshold in candidates:
                left = [i for i in indices if X[i][feature] <= threshold]
                right = [i for i in indices if X[i][feature] > threshold]
                if len(left) < self.min_samples_leaf or len(right) < self.min_samples_leaf:
                    continue
                gain = parent_sse - self._sse(y, left) - self._sse(y, right)
                if gain > best_gain:
                    best_gain, best_feature, best_threshold = gain, feature, threshold
        if best_feature is None or best_threshold is None:
            return node
        gains[best_feature] += best_gain
        left_idx = [i for i in indices if X[i][best_feature] <= best_threshold]
        right_idx = [i for i in indices if X[i][best_feature] > best_threshold]
        node.feature = best_feature
        node.threshold = best_threshold
        node.left = self._build(X, y, left_idx, depth=depth + 1, gains=gains)
        node.right = self._build(X, y, right_idx, depth=depth + 1, gains=gains)
        return node

    def _candidates(self, values: list[float]) -> list[float]:
        if len(values) <= 8:
            return [(a + b) / 2 for a, b in zip(values, values[1:], strict=False)]
        step = max(1, len(values) // 8)
        picked = values[::step][:8]
        return [(a + b) / 2 for a, b in zip(picked, picked[1:], strict=False)]

    @staticmethod
    def _sse(y: list[float], indices: list[int]) -> float:
        if not indices:
            return 0.0
        mean = sum(y[i] for i in indices) / len(indices)
        return sum((y[i] - mean) ** 2 for i in indices)

    def _predict_tree(self, node: _Node, row: list[float]) -> float:
        current = node
        while (
            current.feature is not None and current.left is not None and current.right is not None
        ):
            current = (
                current.left
                if row[current.feature] <= (current.threshold or 0.0)
                else current.right
            )
        return current.value

    def predict(self, X: list[list[float]]) -> list[float]:
        """Predict each row."""
        return [
            self.base + sum(self.learning_rate * self._predict_tree(t, row) for t in self.trees)
            for row in X
        ]

    def to_dict(self) -> dict[str, Any]:
        """Serialise the fitted model."""
        return {
            "kind": "local-gradient-boosting",
            "n_estimators": self.n_estimators,
            "learning_rate": self.learning_rate,
            "max_depth": self.max_depth,
            "min_samples_leaf": self.min_samples_leaf,
            "subsample": self.subsample,
            "random_state": self.random_state,
            "feature_names": self.feature_names,
            "base": self.base,
            "trees": [self._node_dict(t) for t in self.trees],
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> LocalGradientBoostingRegressor:
        """Restore a serialised model."""
        model = cls(
            n_estimators=payload["n_estimators"],
            learning_rate=payload["learning_rate"],
            max_depth=payload["max_depth"],
            min_samples_leaf=payload["min_samples_leaf"],
            subsample=payload["subsample"],
            random_state=payload["random_state"],
            feature_names=payload.get("feature_names", []),
            base=payload.get("base", 0.0),
        )
        model.trees = [model._node_from_dict(t) for t in payload.get("trees", [])]
        return model

    @classmethod
    def _node_dict(cls, node: _Node) -> dict[str, Any]:
        return {
            "value": node.value,
            "feature": node.feature,
            "threshold": node.threshold,
            "left": cls._node_dict(node.left) if node.left else None,
            "right": cls._node_dict(node.right) if node.right else None,
        }

    @classmethod
    def _node_from_dict(cls, payload: dict[str, Any]) -> _Node:
        return _Node(
            value=payload["value"],
            feature=payload.get("feature"),
            threshold=payload.get("threshold"),
            left=cls._node_from_dict(payload["left"]) if payload.get("left") else None,
            right=cls._node_from_dict(payload["right"]) if payload.get("right") else None,
        )


def r2_score(actual: list[float], predicted: list[float]) -> float:
    """Coefficient of determination, safe for short vectors."""
    if len(actual) < 2:
        return 0.0
    mean = sum(actual) / len(actual)
    total = sum((a - mean) ** 2 for a in actual)
    residual = sum((a - p) ** 2 for a, p in zip(actual, predicted, strict=False))
    return 1.0 - residual / total if total else 0.0


def mae(actual: list[float], predicted: list[float]) -> float:
    """Mean absolute error."""
    return sum(abs(a - p) for a, p in zip(actual, predicted, strict=False)) / max(len(actual), 1)


def is_sklearn_model(model: Any) -> bool:
    """Whether the fitted model came from scikit-learn."""
    return type(model).__module__.startswith("sklearn")


def finite(value: float) -> float:
    """Clamp non-finite model output to zero."""
    return value if math.isfinite(value) else 0.0
