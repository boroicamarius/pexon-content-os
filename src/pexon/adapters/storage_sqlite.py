"""SQLite storage adapter, the default local persistence path."""

from __future__ import annotations

import sqlite3
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from pexon.adapters._storage_common import (
    decode_row,
    encode_row,
    order_column,
    primary_key,
    table_name,
)
from pexon.config.settings import Settings
from pexon.ports.errors import StorageError
from pexon.ports.storage import StoragePort

AVAILABLE = True
UNAVAILABLE_REASON = ""


class SqliteStorage(StoragePort):
    """Relational persistence in one SQLite file."""

    def __init__(self, settings: Settings) -> None:
        self._path: Path = settings.sqlite_path
        self._schema: Path = settings.schema_file

    @property
    def provider(self) -> str:
        return "sqlite"

    def _connect(self) -> sqlite3.Connection:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self._path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def setup(self) -> None:
        """Apply db/schema.sql repeatedly."""
        if not self._schema.exists():
            raise StorageError(f"missing schema: {self._schema}")
        try:
            with self._connect() as connection:
                connection.executescript(self._schema.read_text(encoding="utf-8"))
        except Exception as exc:
            raise StorageError(f"sqlite schema failed: {exc}") from exc

    def write(self, table: str, row: Mapping[str, Any]) -> None:
        """Upsert one allow-listed row."""
        table = table_name(table)
        data = encode_row(table, row)
        if not data:
            raise StorageError("empty row")
        columns = list(data)
        placeholders = ", ".join("?" for _ in columns)
        updates = ", ".join(f"{c}=excluded.{c}" for c in columns if c != primary_key(table))
        sql = (
            f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders}) "
            f"ON CONFLICT({primary_key(table)}) DO UPDATE SET {updates}"
            if updates
            else f"INSERT OR REPLACE INTO {table} ({', '.join(columns)}) VALUES ({placeholders})"
        )
        try:
            with self._connect() as connection:
                connection.execute(sql, [data[c] for c in columns])
        except Exception as exc:
            raise StorageError(f"sqlite write failed for {table}: {exc}") from exc

    def read(self, table: str, record_id: str) -> dict[str, Any] | None:
        """Read one row by id."""
        table = table_name(table)
        try:
            with self._connect() as connection:
                cursor = connection.execute(
                    f"SELECT * FROM {table} WHERE {primary_key(table)} = ?", (record_id,)
                )
                row = cursor.fetchone()
        except Exception as exc:
            raise StorageError(f"sqlite read failed for {table}: {exc}") from exc
        return decode_row(table, dict(row)) if row else None

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
        table = table_name(table)
        clauses: list[str] = []
        params: list[Any] = []
        for key, value in equals.items():
            clauses.append(f"{key} = ?")
            params.append(value)
        sql = f"SELECT * FROM {table}"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        if order_by:
            sql += f" ORDER BY {order_column(table, order_by)} {'DESC' if desc else 'ASC'}"
        if limit is not None:
            sql += " LIMIT ?"
            params.append(int(limit))
        try:
            with self._connect() as connection:
                rows = connection.execute(sql, params).fetchall()
        except Exception as exc:
            raise StorageError(f"sqlite find failed for {table}: {exc}") from exc
        return [decode_row(table, dict(row)) for row in rows]

    def latest(
        self, table: str, *, order_by: str = "created_at", **equals: Any
    ) -> dict[str, Any] | None:
        """Read the newest matching row."""
        rows = self.find(table, limit=1, order_by=order_by, desc=True, **equals)
        return rows[0] if rows else None

    def probe(self) -> bool:
        """Run a trivial query."""
        try:
            with self._connect() as connection:
                connection.execute("SELECT 1").fetchone()
        except Exception as exc:
            raise StorageError(f"sqlite probe failed: {exc}") from exc
        return True
