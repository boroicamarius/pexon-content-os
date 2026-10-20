"""CSV analytics adapter: the documented zero-key analytics path."""

from __future__ import annotations

import csv
from datetime import UTC, datetime
from pathlib import Path

from pexon.config.settings import Settings
from pexon.models.performance import Performance, PerformanceBundle
from pexon.ports.analytics import AnalyticsPort
from pexon.ports.errors import AnalyticsError

AVAILABLE = True
UNAVAILABLE_REASON = ""
_COLUMNS = ("article_id", "clicks", "impressions", "position", "measured_at", "page_url")


class CsvAnalytics(AnalyticsPort):
    """Reads real exported metrics from data/analytics.csv."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._path: Path = settings.analytics_file

    @property
    def provider(self) -> str:
        return "csv"

    def fetch(
        self, article_id: str, *, window_days: int, page_url: str | None = None
    ) -> PerformanceBundle:
        """Filter CSV rows for the article and window."""
        if not self._path.exists():
            return PerformanceBundle(
                article_id=article_id, rows=(), clicks=0.0, impressions=0.0, position=0.0
            )
        cutoff = datetime.now(UTC).timestamp() - window_days * 86400
        rows: list[Performance] = []
        try:
            with self._path.open(newline="", encoding="utf-8") as handle:
                for item in csv.DictReader(handle):
                    if item.get("article_id") != article_id:
                        continue
                    measured = self._parse_dt(item.get("measured_at", ""))
                    if measured.timestamp() < cutoff:
                        continue
                    rows.append(
                        Performance(
                            article_id=article_id,
                            clicks=float(item.get("clicks") or 0),
                            impressions=float(item.get("impressions") or 0),
                            position=float(item.get("position") or 0),
                            measured_at=measured,
                            source=self.provider,
                            page_url=item.get("page_url") or (page_url or ""),
                        )
                    )
        except Exception as exc:
            raise AnalyticsError(f"csv analytics read failed: {exc}") from exc
        return self._bundle(article_id, rows)

    @staticmethod
    def _parse_dt(value: str) -> datetime:
        if not value:
            return datetime.now(UTC)
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
        except ValueError:
            return datetime.now(UTC)

    @staticmethod
    def _bundle(article_id: str, rows: list[Performance]) -> PerformanceBundle:
        clicks = sum(r.clicks for r in rows)
        impressions = sum(r.impressions for r in rows)
        weighted = sum(r.position * max(r.impressions, 1.0) for r in rows)
        denom = sum(max(r.impressions, 1.0) for r in rows) or 1.0
        return PerformanceBundle(
            article_id=article_id,
            rows=tuple(rows),
            clicks=clicks,
            impressions=impressions,
            position=weighted / denom if rows else 0.0,
        )

    def probe(self) -> bool:
        """Verify the CSV is present and has the expected header."""
        if not self._path.exists():
            raise AnalyticsError(f"missing analytics csv: {self._path}")
        with self._path.open(newline="", encoding="utf-8") as handle:
            header = next(csv.reader(handle), [])
        missing = [c for c in _COLUMNS[:5] if c not in header]
        if missing:
            raise AnalyticsError(f"analytics csv missing columns: {missing}")
        return True
