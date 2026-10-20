"""CSV keyword-demand adapter: the zero-key portfolio source."""
from __future__ import annotations

import csv
from pathlib import Path

from pexon.config.settings import Settings
from pexon.models.portfolio import KeywordDemand
from pexon.ports.errors import ProviderError
from pexon.ports.keywords import KeywordPort

AVAILABLE = True
UNAVAILABLE_REASON = ""
_COLUMNS = ("keyword", "volume", "difficulty", "cpc", "intent", "funnel_stage", "cluster")


class CsvKeywordDemand(KeywordPort):
    """Reads real search-demand exports from data/keyword_demand.csv."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._path: Path = settings.keyword_path

    @property
    def provider(self) -> str:
        return "csv"

    def demand(self, seeds: list[str], limit: int) -> list[KeywordDemand]:
        """Filter the CSV by seed text and return measured rows."""
        if not self._path.exists():
            return []
        rows: list[KeywordDemand] = []
        try:
            with self._path.open(newline="", encoding="utf-8") as handle:
                for item in csv.DictReader(handle):
                    keyword = item.get("keyword", "").strip()
                    if not keyword:
                        continue
                    if seeds and not any(seed.lower() in keyword.lower() for seed in seeds):
                        continue
                    rows.append(KeywordDemand(
                        keyword=keyword,
                        volume=int(float(item.get("volume") or 0)),
                        difficulty=float(item.get("difficulty") or 0),
                        cpc=float(item.get("cpc") or 0),
                        intent=item.get("intent") or "informational",
                        funnel_stage=item.get("funnel_stage") or "top",
                        cluster=item.get("cluster") or "",
                        source=self.provider,
                    ))
        except Exception as exc:
            raise ProviderError(f"keyword csv read failed: {exc}") from exc
        rows.sort(key=lambda row: row.volume, reverse=True)
        return rows[:limit]

    def probe(self) -> bool:
        """Verify the CSV header."""
        if not self._path.exists():
            raise ProviderError(f"missing keyword csv: {self._path}")
        with self._path.open(newline="", encoding="utf-8") as handle:
            header = next(csv.reader(handle), [])
        missing = [column for column in _COLUMNS if column not in header]
        if missing:
            raise ProviderError(f"keyword csv missing columns: {missing}")
        return True
