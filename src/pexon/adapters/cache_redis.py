"""Optional Redis cache adapter."""

from __future__ import annotations

import json
from typing import Any

from pexon.config.settings import Settings
from pexon.ports.cache import CachePort
from pexon.ports.errors import ProviderError

try:
    import redis

    _HAS_REDIS = True
except ImportError:
    redis = None  # type: ignore[assignment]
    _HAS_REDIS = False

AVAILABLE = _HAS_REDIS
UNAVAILABLE_REASON = "install redis"


class RedisCache(CachePort):
    """Redis-backed JSON cache."""

    def __init__(self, settings: Settings) -> None:
        if not settings.redis_url:
            raise ProviderError("REDIS_URL is required for redis cache")
        self._client = (
            redis.Redis.from_url(settings.redis_url, decode_responses=True) if _HAS_REDIS else None
        )
        self._default_ttl = settings.cache_ttl_seconds

    @property
    def provider(self) -> str:
        return "redis"

    def get_json(self, key: str) -> Any | None:
        """Read and decode one key."""
        raw = self._client.get(key) if self._client else None
        return json.loads(raw) if raw else None

    def set_json(self, key: str, value: Any, ttl_seconds: int | None = None) -> None:
        """Write one key with TTL."""
        if self._client is None:
            raise ProviderError(UNAVAILABLE_REASON)
        ttl = self._default_ttl if ttl_seconds is None else ttl_seconds
        self._client.set(key, json.dumps(value, ensure_ascii=False, default=str), ex=ttl or None)

    def probe(self) -> bool:
        """Ping Redis."""
        if self._client is None:
            raise ProviderError(UNAVAILABLE_REASON)
        return bool(self._client.ping())
