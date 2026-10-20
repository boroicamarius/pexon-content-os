"""PostgreSQL storage adapter selected by DATABASE_URL."""

from __future__ import annotations

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

try:
    import psycopg
    from psycopg.rows import dict_row

    _HAS_PSYCOPG = True
except ImportError:
    psycopg = None  # type: ignore[assignment]
    dict_row = None  # type: ignore[assignment]
    _HAS_PSYCOPG = False

AVAILABLE = _HAS_PSYCOPG
UNAVAILABLE_REASON = "install psycopg[binary]"


class PostgresStorage(StoragePort):
    """Postgres persistence with the same relational contract as SQLite."""

    def __init__(self, settings: Settings) -> None:
        self._url = settings.database_url
        self._schema: Path = settings.schema_file
        if not self._url:
            raise StorageError("DATABASE_URL is required for postgres")

    @property
    def provider(self) -> str:
        return "postgres"

    def _connect(self) -> psycopg.Connection:
        if not _HAS_PSYCOPG:
            raise StorageError(UNAVAILABLE_REASON)
        return psycopg.connect(self._url, row_factory=dict_row)  # type: ignore[union-attr,arg-type]

    def setup(self) -> None:
        """Apply schema statements one by one."""
        if not self._schema.exists():
            raise StorageError(f"missing schema: {self._schema}")
        try:
            with self._connect() as connection:
                with connection.cursor() as cursor:
                    for statement in self._schema.read_text(encoding="utf-8").split(";"):
                        if statement.strip():
                            cursor.execute(statement)
                connection.commit()
        except Exception as exc:
            raise StorageError(f"postgres schema failed: {exc}") from exc

    def write(self, table: str, row: Mapping[str, Any]) -> None:
        """Upsert one allow-listed row."""
        table = table_name(table)
        data = encode_row(table, row)
        columns = list(data)
        placeholders = ", ".join("%s" for _ in columns)
        updates = ", ".join(f"{c}=EXCLUDED.{c}" for c in columns if c != primary_key(table))
        sql = (
            f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders}) "
            f"ON CONFLICT ({primary_key(table)}) DO UPDATE SET {updates}"
            if updates
            else f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders}) "
            f"ON CONFLICT ({primary_key(table)}) DO NOTHING"
        )
        try:
            with self._connect() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(sql, [data[c] for c in columns])
                connection.commit()
        except Exception as exc:
            raise StorageError(f"postgres write failed for {table}: {exc}") from exc

    def read(self, table: str, record_id: str) -> dict[str, Any] | None:
        """Read one row by id."""
        table = table_name(table)
        try:
            with self._connect() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        f"SELECT * FROM {table} WHERE {primary_key(table)} = %s", (record_id,)
                    )
                    row = cursor.fetchone()
        except Exception as exc:
            raise StorageError(f"postgres read failed for {table}: {exc}") from exc
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
            clauses.append(f"{key} = %s")
            params.append(value)
        sql = f"SELECT * FROM {table}"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        if order_by:
            sql += f" ORDER BY {order_column(table, order_by)} {'DESC' if desc else 'ASC'}"
        if limit is not None:
            sql += " LIMIT %s"
            params.append(int(limit))
        try:
            with self._connect() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(sql, params)
                    rows = cursor.fetchall()
        except Exception as exc:
            raise StorageError(f"postgres find failed for {table}: {exc}") from exc
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
                with connection.cursor() as cursor:
                    cursor.execute("SELECT 1")
                    cursor.fetchone()
        except Exception as exc:
            raise StorageError(f"postgres probe failed: {exc}") from exc
        return True
