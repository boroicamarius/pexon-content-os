"""In-process run metrics, printed at the end of every run."""

from __future__ import annotations

import threading
from collections import defaultdict

from pexon.ports.llm import LLMResult


class MetricsCollector:
    """Thread-safe counters and token accounting for one run."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters: dict[tuple[str, tuple[tuple[str, str], ...]], float] = defaultdict(float)
        self._tokens: dict[tuple[str, str], dict[str, int]] = defaultdict(
            lambda: {"in": 0, "out": 0}
        )

    def inc(self, name: str, labels: dict[str, str] | None = None, amount: float = 1.0) -> None:
        """Increment a labelled counter."""
        key = (name, tuple(sorted((labels or {}).items())))
        with self._lock:
            self._counters[key] += amount

    def record_llm(self, result: LLMResult) -> None:
        """Record calls and tokens per provider/model."""
        self.inc("llm_calls", {"provider": result.provider, "model": result.model})
        with self._lock:
            bucket = self._tokens[(result.provider, result.model)]
            bucket["in"] += result.tokens_in
            bucket["out"] += result.tokens_out

    def count(self, name: str, labels: dict[str, str] | None = None) -> float:
        """Read one counter."""
        key = (name, tuple(sorted((labels or {}).items())))
        with self._lock:
            return self._counters.get(key, 0.0)

    def snapshot(self) -> dict[str, object]:
        """Return a JSON-safe metrics snapshot."""
        with self._lock:
            counters: dict[str, dict[str, object]] = {
                name: {
                    "labels": dict(labels),
                    "value": round(value, 4),
                }
                for (name, labels), value in sorted(self._counters.items())
            }
            tokens: dict[str, dict[str, int]] = {
                f"{provider}/{model}": dict(values)
                for (provider, model), values in sorted(self._tokens.items())
            }

        def total(name: str) -> int:
            return int(sum(float(v["value"]) for n, v in counters.items() if n == name))

        return {
            "counters": counters,
            "tokens": tokens,
            "llm_calls": total("llm_calls"),
            "tokens_in": sum(v["in"] for v in tokens.values()),
            "tokens_out": sum(v["out"] for v in tokens.values()),
            "search_calls": total("search_calls"),
            "fetch_ok": total("fetch_ok"),
            "fetch_fail": total("fetch_fail"),
            "gate_failures": total("gate_failures"),
            "retry_count": total("retry_count"),
            "provider_fallbacks": total("provider_fallbacks"),
        }

    def render(self) -> str:
        """Render the compact end-of-run metrics line."""
        snap = self.snapshot()
        return (
            f"llm_calls={snap['llm_calls']} tokens_in={snap['tokens_in']} "
            f"tokens_out={snap['tokens_out']} search={snap['search_calls']} "
            f"fetch_ok={snap['fetch_ok']} fetch_fail={snap['fetch_fail']} "
            f"gate_failures={snap['gate_failures']} retries={snap['retry_count']} "
            f"fallbacks={snap['provider_fallbacks']}"
        )
