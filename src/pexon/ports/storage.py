"""Storage port."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from typing import Any


class StoragePort(ABC):
    """Small relational persistence surface shared by SQLite and Postgres."""

    @property
    @abstractmethod
    def provider(self) -> str:
        """Registered provider name."""

    @abstractmethod
    def setup(self) -> None:
        """Apply the idempotent schema."""

    @abstractmethod
    def write(self, table: str, row: Mapping[str, Any]) -> None:
        """Upsert one row in an allow-listed table."""

    @abstractmethod
    def read(self, table: str, record_id: str) -> dict[str, Any] | None:
        """Read one row by primary key."""

    @abstractmethod
    def find(
        self,
        table: str,
        *,
        limit: int | None = None,
        order_by: str | None = None,
        desc: bool = True,
        **equals: Any,
    ) -> list[dict[str, Any]]:
        """Find rows by equality filters."""

    @abstractmethod
    def latest(
        self,
        table: str,
        *,
        order_by: str = "created_at",
        **equals: Any,
    ) -> dict[str, Any] | None:
        """Read the newest matching row."""

    @abstractmethod
    def probe(self) -> bool:
        """Verify the backing database."""
