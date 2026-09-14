from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from gptina_memory_engine.archive import archive_file, sha256_file
from gptina_memory_engine.builder import build_database
from gptina_memory_engine.normalized import NormalizedRecord
from gptina_memory_engine.store import MemoryStore


class MemoryEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.manifest = self.root / "manifest.json"
        self.records = self.root / "records.jsonl"
        self.db = self.root / "memory.sqlite3"
        self.manifest.write_text(
            json.dumps(
                {
                    "source_id": "synthetic-test-source",
                    "source_kind": "synthetic_fixture",
                    "locator": "tests/test_core.py",
                    "archive_sha256": None,
                    "imported_at_utc": "2026-09-14T05:00:00Z",
                    "metadata": {"fixture": True},
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        rows = [
            {
                "record_id": "r1",
                "source_id": "synthetic-test-source",
                "source_record_key": "m1",
                "conversation_key": "c1",
                "sequence_index": 0,
                "sequence_verified": True,
                "role": "user",
                "created_at_utc": "2026-09-14T05:01:00Z",
                "content_text": "alpha exact Needle",
                "metadata": {"fixture": 1},
            },
            {
                "record_id": "r2",
                "source_id": "synthetic-test-source",
                "source_record_key": "m2",
                "conversation_key": "c1",
                "sequence_index": 1,
                "sequence_verified": True,
                "role": "assistant",
                "created_at_utc": "2026-09-14T05:02:00Z",
                "content_text": "beta alpha",
                "metadata": {"fixture": 2},
            },
            {
                "record_id": "r3",
                "source_id": "synthetic-test-source",
                "source_record_key": "m3",
                "conversation_key": None,
                "sequence_index": None,
                "sequence_verified": False,
                "role": None,
                "created_at_utc": None,
                "content_text": "gamma",
                "metadata": {"fixture": 3},
            },
        ]
        with self.records.open("w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_record_digest_covers_metadata_and_role(self) -> None:
        base = {
            "record_id": "x",
            "source_id": "s",
            "content_text": "same",
            "metadata": {"a": 1},
            "role": "user",
        }
        a = NormalizedRecord.from_dict(base)
        b = NormalizedRecord.from_dict({**base, "role": "assistant"})
        c = NormalizedRecord.from_dict({**base, "metadata": {"a": 2}})
        self.assertNotEqual(a.record_sha256, b.record_sha256)
        self.assertNotEqual(a.record_sha256, c.record_sha256)

    def test_build_search_context_and_timeline(self) -> None:
        result = build_database(self.manifest, self.records, self.db)
        self.assertEqual(result, {"sources": 1, "records": 3})
        store = MemoryStore(self.db)
        try:
            self.assertEqual(store.status()["mode"], "read-only")
            hits = store.search("alpha")
            self.assertEqual({h["record_id"] for h in hits}, {"r1", "r2"})
            exact = store.find_exact("Needle")
            self.assertEqual([r["record_id"] for r in exact], ["r1"])
            ctx = store.context("r2", before=1, after=1)
            self.assertTrue(ctx["context_available"])
            self.assertEqual([r["record_id"] for r in ctx["before"]], ["r1"])
            unavailable = store.context("r3")
            self.assertFalse(unavailable["context_available"])
            timeline = store.timeline("2026-09-14T05:00:00Z", "2026-09-14T05:03:00Z")
            self.assertEqual([r["record_id"] for r in timeline], ["r1", "r2"])
        finally:
            store.close()

    def test_runtime_database_is_query_only(self) -> None:
        build_database(self.manifest, self.records, self.db)
        store = MemoryStore(self.db)
        try:
            with self.assertRaises(sqlite3.OperationalError):
                store.conn.execute("DELETE FROM records")
        finally:
            store.close()

    def test_builder_refuses_overwrite(self) -> None:
        build_database(self.manifest, self.records, self.db)
        with self.assertRaises(FileExistsError):
            build_database(self.manifest, self.records, self.db)

    def test_unverified_sequence_never_creates_context(self) -> None:
        build_database(self.manifest, self.records, self.db)
        store = MemoryStore(self.db)
        try:
            ctx = store.context("r3")
            self.assertEqual(ctx["reason"], "sequence_not_verified")
            self.assertEqual(ctx["before"], [])
            self.assertEqual(ctx["after"], [])
        finally:
            store.close()

    def test_archive_is_content_addressed_and_verified(self) -> None:
        source = self.root / "raw.bin"
        source.write_bytes(b"abc\x00def")
        info = archive_file(source, self.root / "archive")
        archived = Path(str(info["archive_path"]))
        self.assertEqual(sha256_file(source), sha256_file(archived))
        self.assertEqual(info["size_bytes"], 7)


if __name__ == "__main__":
    unittest.main()
