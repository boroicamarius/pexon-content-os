"""Shared table allow-list and value normalisation for SQL storage."""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import date, datetime
from pathlib import Path
from typing import Any

_TABLES: dict[str, str] = {
    "topics": "id",
    "research_snapshots": "id",
    "articles": "id",
    "drafts": "id",
    "predictions": "id",
    "performance": "id",
    "features": "id",
    "weights": "id",
    "model_cards": "id",
    "events": "id",
    "prompt_variants": "id",
    "leads": "id",
    "geo_visibility": "id",
    "article_costs": "id",
    "reviews": "id",
    "funnel_reports": "id",
    "content_plans": "id",
}

_JSON_COLUMNS: dict[str, set[str]] = {
    "research_snapshots": {"facts_json", "sources_json"},
    "articles": {"provider_config_json"},
    "drafts": {"signals_json"},
    "predictions": {"ci_json"},
    "features": {"features_json"},
    "weights": {"values_json", "metrics_json", "provider_config_json"},
    "model_cards": {"features_json", "metrics_json", "provider_config_json"},
    "events": {"payload_json"},
    "geo_visibility": {"citations_json"},
    "funnel_reports": {"report_json"},
    "content_plans": {"plan_json"},
}

_ORDER_COLUMNS: dict[str, set[str]] = {
    "research_snapshots": {"created_at", "snapshot_hash"},
    "articles": {"created_at", "title_de", "status"},
    "drafts": {"created_at", "version"},
    "predictions": {"created_at"},
    "performance": {"measured_at", "created_at"},
    "features": {"created_at"},
    "weights": {"trained_at", "created_at"},
    "model_cards": {"created_at", "trained_at"},
    "events": {"ts"},
    "prompt_variants": {"created_at", "version"},
    "topics": {"created_at"},
    "leads": {"created_at"},
    "geo_visibility": {"measured_at"},
    "article_costs": {"created_at"},
    "reviews": {"created_at"},
    "funnel_reports": {"created_at"},
    "content_plans": {"created_at"},
}


def table_name(table: str) -> str:
    """Validate a table identifier against the allow-list."""
    if table not in _TABLES:
        raise ValueError(f"unknown table: {table}")
    return table


def primary_key(table: str) -> str:
    """Return the table's primary key column."""
    return _TABLES[table_name(table)]


def order_column(table: str, column: str) -> str:
    """Validate an order-by column."""
    table_name(table)
    if column not in _ORDER_COLUMNS.get(table, set()):
        raise ValueError(f"unknown order column: {table}.{column}")
    return column


def encode_value(value: Any) -> Any:
    """Normalise Python values for SQL parameters."""
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, ensure_ascii=False, default=str)
    if isinstance(value, bool):
        return 1 if value else 0
    return value


def encode_row(table: str, row: Mapping[str, Any]) -> dict[str, Any]:
    """Normalise every value, encoding declared JSON columns."""
    encoded: dict[str, Any] = {}
    for key, value in row.items():
        encode_as_json = key in _JSON_COLUMNS.get(table, set()) and not isinstance(value, str)
        encoded[key] = (
            json.dumps(value, ensure_ascii=False, default=str)
            if encode_as_json
            else encode_value(value)
        )
    return encoded


def decode_row(table: str, row: Mapping[str, Any]) -> dict[str, Any]:
    """Decode JSON columns into Python values."""
    output = dict(row)
    for column in _JSON_COLUMNS.get(table, set()):
        value = output.get(column)
        if isinstance(value, str) and value:
            try:
                output[column] = json.loads(value)
            except json.JSONDecodeError:
                pass
    return output
