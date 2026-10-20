"""SQLite-backed LangGraph checkpointer with the SqliteSaver public surface."""

from __future__ import annotations

import json
import sqlite3
import threading
from collections.abc import Iterator
from contextlib import AbstractContextManager
from pathlib import Path
from typing import Any

from langgraph.checkpoint.base import (
    ChannelVersions,
    Checkpoint,
    CheckpointMetadata,
    CheckpointTuple,
)
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.serde.base import SerializerProtocol

_SCHEMA = """
CREATE TABLE IF NOT EXISTS lg_checkpoints (
    thread_id TEXT NOT NULL,
    checkpoint_ns TEXT NOT NULL,
    checkpoint_id TEXT NOT NULL,
    parent_id TEXT,
    checkpoint_type TEXT NOT NULL,
    checkpoint_blob BLOB NOT NULL,
    metadata_type TEXT NOT NULL,
    metadata_blob BLOB NOT NULL,
    PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id)
);
CREATE TABLE IF NOT EXISTS lg_blobs (
    thread_id TEXT NOT NULL,
    checkpoint_ns TEXT NOT NULL,
    channel TEXT NOT NULL,
    version_json TEXT NOT NULL,
    value_type TEXT NOT NULL,
    value_blob BLOB NOT NULL,
    PRIMARY KEY (thread_id, checkpoint_ns, channel, version_json)
);
CREATE TABLE IF NOT EXISTS lg_writes (
    thread_id TEXT NOT NULL,
    checkpoint_ns TEXT NOT NULL,
    checkpoint_id TEXT NOT NULL,
    task_id TEXT NOT NULL,
    idx INTEGER NOT NULL,
    channel TEXT NOT NULL,
    value_type TEXT NOT NULL,
    value_blob BLOB NOT NULL,
    task_path TEXT NOT NULL,
    PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id, task_id, idx)
);
"""


class SqliteSaver(InMemorySaver, AbstractContextManager):
    """Persists LangGraph checkpoints through the same API as the official saver."""

    def __init__(self, conn: sqlite3.Connection, serde: SerializerProtocol | None = None) -> None:
        super().__init__(serde=serde)
        self._conn = conn
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.RLock()
        self._loaded: set[str] = set()
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    @classmethod
    def from_conn_string(
        cls, conn_string: str, serde: SerializerProtocol | None = None
    ) -> SqliteSaver:
        """Open or create a checkpoint database."""
        path = Path(conn_string)
        path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(str(path), check_same_thread=False, timeout=30)
        connection.execute("PRAGMA journal_mode=WAL")
        return cls(connection, serde=serde)

    def __enter__(self) -> SqliteSaver:
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> bool | None:
        self._conn.close()
        return None

    def setup(self) -> None:
        """Ensure the checkpoint tables exist."""
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._conn.commit()

    def _load_thread(self, thread_id: str) -> None:
        if thread_id in self._loaded:
            return
        with self._lock:
            if thread_id in self._loaded:
                return
            checkpoints = self._conn.execute(
                "SELECT * FROM lg_checkpoints WHERE thread_id = ?", (thread_id,)
            ).fetchall()
            if checkpoints:
                for row in checkpoints:
                    ns = row["checkpoint_ns"]
                    self.storage[thread_id][ns][row["checkpoint_id"]] = (
                        (row["checkpoint_type"], bytes(row["checkpoint_blob"])),
                        (row["metadata_type"], bytes(row["metadata_blob"])),
                        row["parent_id"],
                    )
            blobs = self._conn.execute(
                "SELECT * FROM lg_blobs WHERE thread_id = ?", (thread_id,)
            ).fetchall()
            for row in blobs:
                version = json.loads(row["version_json"])
                self.blobs[(thread_id, row["checkpoint_ns"], row["channel"], version)] = (
                    row["value_type"],
                    bytes(row["value_blob"]),
                )
            writes = self._conn.execute(
                "SELECT * FROM lg_writes WHERE thread_id = ?", (thread_id,)
            ).fetchall()
            for row in writes:
                outer = (thread_id, row["checkpoint_ns"], row["checkpoint_id"])
                inner = (row["task_id"], int(row["idx"]))
                self.writes[outer][inner] = (
                    row["task_id"],
                    row["channel"],
                    (row["value_type"], bytes(row["value_blob"])),
                    row["task_path"],
                )
            self._loaded.add(thread_id)

    def _persist_thread(self, thread_id: str) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM lg_checkpoints WHERE thread_id = ?", (thread_id,))
            self._conn.execute("DELETE FROM lg_blobs WHERE thread_id = ?", (thread_id,))
            self._conn.execute("DELETE FROM lg_writes WHERE thread_id = ?", (thread_id,))
            for ns, checkpoints in self.storage.get(thread_id, {}).items():
                for checkpoint_id, (checkpoint, metadata, parent) in checkpoints.items():
                    self._conn.execute(
                        "INSERT INTO lg_checkpoints VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            thread_id,
                            ns,
                            checkpoint_id,
                            parent,
                            checkpoint[0],
                            sqlite3.Binary(checkpoint[1]),
                            metadata[0],
                            sqlite3.Binary(metadata[1]),
                        ),
                    )
            for (blob_thread, ns, channel, version), (value_type, value) in self.blobs.items():
                if blob_thread != thread_id:
                    continue
                self._conn.execute(
                    "INSERT INTO lg_blobs VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        thread_id,
                        ns,
                        channel,
                        json.dumps(version),
                        value_type,
                        sqlite3.Binary(value),
                    ),
                )
            for (write_thread, ns, checkpoint_id), items in self.writes.items():
                if write_thread != thread_id:
                    continue
                for (task_id, idx), (_, channel, typed_value, task_path) in items.items():
                    self._conn.execute(
                        "INSERT INTO lg_writes VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            thread_id,
                            ns,
                            checkpoint_id,
                            task_id,
                            idx,
                            channel,
                            typed_value[0],
                            sqlite3.Binary(typed_value[1]),
                            task_path,
                        ),
                    )
            self._conn.commit()
            self._loaded.add(thread_id)

    def get_tuple(self, config: dict) -> CheckpointTuple | None:
        thread_id = config["configurable"]["thread_id"]
        self._load_thread(thread_id)
        return super().get_tuple(config)

    def list(
        self,
        config: dict | None,
        *,
        filter: dict[str, Any] | None = None,
        before: dict | None = None,
        limit: int | None = None,
    ) -> Iterator[CheckpointTuple]:
        for row in self._conn.execute("SELECT DISTINCT thread_id FROM lg_checkpoints").fetchall():
            self._load_thread(row["thread_id"])
        yield from super().list(config, filter=filter, before=before, limit=limit)

    def put(
        self,
        config: dict,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> dict:
        thread_id = config["configurable"]["thread_id"]
        self._load_thread(thread_id)
        result = super().put(config, checkpoint, metadata, new_versions)
        self._persist_thread(thread_id)
        return result

    def put_writes(
        self, config: dict, writes: list[tuple[str, Any]], task_id: str, task_path: str = ""
    ) -> None:
        thread_id = config["configurable"]["thread_id"]
        self._load_thread(thread_id)
        super().put_writes(config, writes, task_id, task_path)
        self._persist_thread(thread_id)

    def delete_thread(self, thread_id: str) -> None:
        self._load_thread(thread_id)
        super().delete_thread(thread_id)
        with self._lock:
            for table in ("lg_checkpoints", "lg_blobs", "lg_writes"):
                self._conn.execute(f"DELETE FROM {table} WHERE thread_id = ?", (thread_id,))
            self._conn.commit()
            self._loaded.discard(thread_id)
