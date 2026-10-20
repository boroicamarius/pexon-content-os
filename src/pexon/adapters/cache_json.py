"""Filesystem JSON cache."""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

from pexon.config.settings import Settings
from pexon.ports.cache import CachePort

AVAILABLE = True
UNAVAILABLE_REASON = ""
_SAFE = re.compile(r"[^A-Za-z0-9_.-]+")


class JsonCache(CachePort):
    """One JSON file per key, with TTL metadata."""

    def __init__(self, settings: Settings) -> None:
        self._dir = settings.cache_path
        self._dir.mkdir(parents=True, exist_ok=True)
        self._default_ttl = settings.cache_ttl_seconds

    @property
    def provider(self) -> str:
        return "json"

    def _path(self, key: str) -> Path:
        safe = _SAFE.sub("_", key).strip("._") or "cache"
        return self._dir / f"{safe}.json"

    def get_json(self, key: str) -> Any | None:
        """Read a live cache entry."""
        path = self._path(key)
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        expires = float(payload.get("expires_at", 0))
        if expires and expires < time.time():
            path.unlink(missing_ok=True)
            return None
        return payload.get("value")

    def set_json(self, key: str, value: Any, ttl_seconds: int | None = None) -> None:
        """Write a JSON entry atomically."""
        ttl = self._default_ttl if ttl_seconds is None else ttl_seconds
        payload = {
            "key": key,
            "created_at": time.time(),
            "expires_at": time.time() + ttl if ttl > 0 else 0,
            "value": value,
        }
        path = self._path(key)
        temp = path.with_suffix(".tmp")
        temp.write_text(json.dumps(payload, ensure_ascii=False, default=str), encoding="utf-8")
        temp.replace(path)

    def probe(self) -> bool:
        """Round-trip a probe key."""
        key = "__pexon_probe__"
        self.set_json(key, {"ok": True}, ttl_seconds=60)
        return bool(self.get_json(key))
