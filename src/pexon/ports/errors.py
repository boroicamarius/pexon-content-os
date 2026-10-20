"""Stable port error types."""

from __future__ import annotations


class PortError(RuntimeError):
    """Base error raised by an adapter."""


class AdapterUnavailable(PortError):
    """Adapter is registered but its optional dependencies are absent."""


class ProviderError(PortError):
    """A real provider call failed."""


class SearchError(ProviderError):
    """Search provider failed."""


class FetchError(ProviderError):
    """Page fetch failed."""


class StorageError(ProviderError):
    """Storage operation failed."""


class AnalyticsError(ProviderError):
    """Analytics provider failed."""
