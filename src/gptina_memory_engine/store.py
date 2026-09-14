from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

EXPECTED_SCHEMA_VERSION = "1"


class MemoryStore:
    """Read-only access to a prebuilt SQLite memory index."""

    def __init__(self, db_path: Path):
        self.db_path = db_path.resolve(strict=True)
        uri = f"file:{self.db_path.as_posix()}?mode=ro"
        self.conn = sqlite3.connect(uri, uri=True, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA query_only = ON")
        self.conn.execute("PRAGMA foreign_keys = ON")
        self._validate()

    def close(self) -> None:
        self.conn.close()

    def _validate(self) -> None:
        version_row = self.conn.execute(
            "SELECT value FROM engine_meta WHERE key = 'schema_version'"
        ).fetchone()
        if version_row is None or version_row[0] != EXPECTED_SCHEMA_VERSION:
            raise RuntimeError(
                f"unsupported database schema version: {None if version_row is None else version_row[0]!r}"
            )
        quick = self.conn.execute("PRAGMA quick_check").fetchone()[0]
        if quick != "ok":
            raise RuntimeError(f"SQLite quick_check failed: {quick}")

    @staticmethod
    def _record(row: sqlite3.Row) -> dict[str, Any]:
        data = dict(row)
        if "metadata_json" in data:
            data["metadata"] = json.loads(data.pop("metadata_json"))
        if "sequence_verified" in data:
            data["sequence_verified"] = bool(data["sequence_verified"])
        return data

    def status(self) -> dict[str, Any]:
        records = self.conn.execute("SELECT COUNT(*) FROM records").fetchone()[0]
        sources = self.conn.execute("SELECT COUNT(*) FROM sources").fetchone()[0]
        return {
            "schema_version": EXPECTED_SCHEMA_VERSION,
            "sources": sources,
            "records": records,
            "mode": "read-only",
        }

    def get_record(self, record_id: str) -> dict[str, Any] | None:
        row = self.conn.execute("SELECT * FROM records WHERE record_id = ?", (record_id,)).fetchone()
        return None if row is None else self._record(row)

    def get_source(self, source_id: str) -> dict[str, Any] | None:
        row = self.conn.execute("SELECT * FROM sources WHERE source_id = ?", (source_id,)).fetchone()
        if row is None:
            return None
        data = dict(row)
        data["metadata"] = json.loads(data.pop("metadata_json"))
        return data

    def search(self, query: str, limit: int = 10, conversation_key: str | None = None) -> list[dict[str, Any]]:
        if not query.strip():
            raise ValueError("query must not be empty")
        limit = max(1, min(int(limit), 100))
        if conversation_key is None:
            rows = self.conn.execute(
                """
                SELECT r.*, bm25(records_fts) AS rank
                FROM records_fts
                JOIN records r ON r.record_id = records_fts.record_id
                WHERE records_fts MATCH ?
                ORDER BY rank, r.record_id
                LIMIT ?
                """,
                (query, limit),
            ).fetchall()
        else:
            rows = self.conn.execute(
                """
                SELECT r.*, bm25(records_fts) AS rank
                FROM records_fts
                JOIN records r ON r.record_id = records_fts.record_id
                WHERE records_fts MATCH ? AND r.conversation_key = ?
                ORDER BY rank, r.record_id
                LIMIT ?
                """,
                (query, conversation_key, limit),
            ).fetchall()
        return [self._record(row) for row in rows]

    def find_exact(self, text: str, limit: int = 20, conversation_key: str | None = None) -> list[dict[str, Any]]:
        if text == "":
            raise ValueError("text must not be empty")
        limit = max(1, min(int(limit), 100))
        if conversation_key is None:
            rows = self.conn.execute(
                """
                SELECT * FROM records
                WHERE instr(content_text, ?) > 0
                ORDER BY COALESCE(created_at_utc, ''), record_id
                LIMIT ?
                """,
                (text, limit),
            ).fetchall()
        else:
            rows = self.conn.execute(
                """
                SELECT * FROM records
                WHERE conversation_key = ? AND instr(content_text, ?) > 0
                ORDER BY COALESCE(created_at_utc, ''), record_id
                LIMIT ?
                """,
                (conversation_key, text, limit),
            ).fetchall()
        return [self._record(row) for row in rows]

    def context(self, record_id: str, before: int = 3, after: int = 3) -> dict[str, Any]:
        before = max(0, min(int(before), 50))
        after = max(0, min(int(after), 50))
        center = self.get_record(record_id)
        if center is None:
            raise KeyError(record_id)
        if not center["sequence_verified"]:
            return {
                "record": center,
                "before": [],
                "after": [],
                "context_available": False,
                "reason": "sequence_not_verified",
            }
        conversation_key = center["conversation_key"]
        seq = center["sequence_index"]
        previous = self.conn.execute(
            """
            SELECT * FROM records
            WHERE conversation_key = ? AND sequence_verified = 1
              AND sequence_index < ?
            ORDER BY sequence_index DESC
            LIMIT ?
            """,
            (conversation_key, seq, before),
        ).fetchall()
        following = self.conn.execute(
            """
            SELECT * FROM records
            WHERE conversation_key = ? AND sequence_verified = 1
              AND sequence_index > ?
            ORDER BY sequence_index ASC
            LIMIT ?
            """,
            (conversation_key, seq, after),
        ).fetchall()
        return {
            "record": center,
            "before": [self._record(row) for row in reversed(previous)],
            "after": [self._record(row) for row in following],
            "context_available": True,
        }

    def timeline(
        self,
        start_utc: str,
        end_utc: str,
        limit: int = 100,
        conversation_key: str | None = None,
    ) -> list[dict[str, Any]]:
        if not start_utc.endswith("Z") or not end_utc.endswith("Z"):
            raise ValueError("timeline bounds must be explicit UTC timestamps ending in 'Z'")
        if start_utc > end_utc:
            raise ValueError("start_utc must be <= end_utc")
        limit = max(1, min(int(limit), 500))
        if conversation_key is None:
            rows = self.conn.execute(
                """
                SELECT * FROM records
                WHERE created_at_utc IS NOT NULL
                  AND created_at_utc >= ? AND created_at_utc <= ?
                ORDER BY created_at_utc, record_id
                LIMIT ?
                """,
                (start_utc, end_utc, limit),
            ).fetchall()
        else:
            rows = self.conn.execute(
                """
                SELECT * FROM records
                WHERE conversation_key = ? AND created_at_utc IS NOT NULL
                  AND created_at_utc >= ? AND created_at_utc <= ?
                ORDER BY created_at_utc, record_id
                LIMIT ?
                """,
                (conversation_key, start_utc, end_utc, limit),
            ).fetchall()
        return [self._record(row) for row in rows]
