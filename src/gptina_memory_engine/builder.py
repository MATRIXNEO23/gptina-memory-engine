from __future__ import annotations

import argparse
import json
import os
import sqlite3
from importlib.resources import files
from pathlib import Path

from .canonical import canonical_json
from .normalized import NormalizedRecord, SourceManifest

SCHEMA_VERSION = "1"


def _schema_sql() -> str:
    return files("gptina_memory_engine").joinpath("schema.sql").read_text(encoding="utf-8")


def _connect_new_database(path: Path) -> sqlite3.Connection:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite existing database: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(_schema_sql())
    return conn


def build_database(manifest_path: Path, records_path: Path, output_path: Path) -> dict[str, int]:
    manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
    source = SourceManifest.from_dict(manifest_data)

    conn = _connect_new_database(output_path)
    count = 0
    try:
        with conn:
            conn.execute("INSERT INTO engine_meta(key, value) VALUES (?, ?)", ("schema_version", SCHEMA_VERSION))
            conn.execute(
                """
                INSERT INTO sources(
                    source_id, source_kind, locator, archive_sha256,
                    imported_at_utc, metadata_json, manifest_sha256
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    source.source_id,
                    source.source_kind,
                    source.locator,
                    source.archive_sha256,
                    source.imported_at_utc,
                    canonical_json(source.metadata),
                    source.manifest_sha256,
                ),
            )

            seen_ids: set[str] = set()
            with records_path.open("r", encoding="utf-8") as f:
                for line_no, line in enumerate(f, start=1):
                    if not line.strip():
                        continue
                    try:
                        record = NormalizedRecord.from_dict(json.loads(line))
                    except Exception as exc:
                        raise ValueError(f"invalid record at line {line_no}: {exc}") from exc
                    if record.source_id != source.source_id:
                        raise ValueError(
                            f"record {record.record_id!r} source_id {record.source_id!r} "
                            f"does not match manifest source_id {source.source_id!r}"
                        )
                    if record.record_id in seen_ids:
                        raise ValueError(f"duplicate record_id in input: {record.record_id}")
                    seen_ids.add(record.record_id)
                    conn.execute(
                        """
                        INSERT INTO records(
                            record_id, source_id, source_record_key, conversation_key,
                            sequence_index, sequence_verified, role, created_at_utc,
                            content_text, content_sha256, metadata_json, record_sha256
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            record.record_id,
                            record.source_id,
                            record.source_record_key,
                            record.conversation_key,
                            record.sequence_index,
                            1 if record.sequence_verified else 0,
                            record.role,
                            record.created_at_utc,
                            record.content_text,
                            record.content_sha256,
                            record.metadata_json,
                            record.record_sha256,
                        ),
                    )
                    conn.execute(
                        "INSERT INTO records_fts(record_id, content_text) VALUES (?, ?)",
                        (record.record_id, record.content_text),
                    )
                    count += 1

            integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
            if integrity != "ok":
                raise RuntimeError(f"SQLite integrity_check failed: {integrity}")
    except Exception:
        conn.close()
        try:
            output_path.unlink()
        except FileNotFoundError:
            pass
        raise
    else:
        conn.close()

    try:
        fd = os.open(str(output_path.parent), os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    except OSError:
        pass

    return {"sources": 1, "records": count}


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a fresh immutable retrieval index from normalized input.")
    parser.add_argument("manifest", type=Path)
    parser.add_argument("records_jsonl", type=Path)
    parser.add_argument("output_db", type=Path)
    args = parser.parse_args()
    result = build_database(args.manifest, args.records_jsonl, args.output_db)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
