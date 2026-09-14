from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from .canonical import canonical_json, digest_object, sha256_text


def validate_utc_timestamp(value: str | None) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise ValueError("created_at_utc must be null or a non-empty string")
    if not value.endswith("Z"):
        raise ValueError("created_at_utc must use explicit UTC and end in 'Z'")
    datetime.fromisoformat(value[:-1] + "+00:00")
    return value


@dataclass(frozen=True)
class SourceManifest:
    source_id: str
    source_kind: str
    locator: str
    imported_at_utc: str
    metadata: dict[str, Any]
    archive_sha256: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SourceManifest":
        required = {"source_id", "source_kind", "locator", "imported_at_utc", "metadata"}
        missing = required - set(data)
        if missing:
            raise ValueError(f"missing source fields: {sorted(missing)}")
        if not isinstance(data["metadata"], dict):
            raise ValueError("source metadata must be an object")
        validate_utc_timestamp(data["imported_at_utc"])
        archive_sha = data.get("archive_sha256")
        if archive_sha is not None and (not isinstance(archive_sha, str) or len(archive_sha) != 64):
            raise ValueError("archive_sha256 must be null or a 64-character hex digest")
        return cls(
            source_id=str(data["source_id"]),
            source_kind=str(data["source_kind"]),
            locator=str(data["locator"]),
            imported_at_utc=str(data["imported_at_utc"]),
            metadata=data["metadata"],
            archive_sha256=archive_sha,
        )

    def digest_payload(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "source_kind": self.source_kind,
            "locator": self.locator,
            "imported_at_utc": self.imported_at_utc,
            "metadata": self.metadata,
            "archive_sha256": self.archive_sha256,
        }

    @property
    def manifest_sha256(self) -> str:
        return digest_object(self.digest_payload())


@dataclass(frozen=True)
class NormalizedRecord:
    record_id: str
    source_id: str
    content_text: str
    metadata: dict[str, Any]
    source_record_key: str | None = None
    conversation_key: str | None = None
    sequence_index: int | None = None
    sequence_verified: bool = False
    role: str | None = None
    created_at_utc: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "NormalizedRecord":
        required = {"record_id", "source_id", "content_text", "metadata"}
        missing = required - set(data)
        if missing:
            raise ValueError(f"missing record fields: {sorted(missing)}")
        if not isinstance(data["metadata"], dict):
            raise ValueError("record metadata must be an object")
        sequence_verified = bool(data.get("sequence_verified", False))
        conversation_key = data.get("conversation_key")
        sequence_index = data.get("sequence_index")
        if sequence_index is not None and (not isinstance(sequence_index, int) or isinstance(sequence_index, bool)):
            raise ValueError("sequence_index must be null or an integer")
        if sequence_verified and (conversation_key is None or sequence_index is None):
            raise ValueError("verified sequence requires conversation_key and sequence_index")
        created_at = validate_utc_timestamp(data.get("created_at_utc"))
        return cls(
            record_id=str(data["record_id"]),
            source_id=str(data["source_id"]),
            content_text=str(data["content_text"]),
            metadata=data["metadata"],
            source_record_key=None if data.get("source_record_key") is None else str(data["source_record_key"]),
            conversation_key=None if conversation_key is None else str(conversation_key),
            sequence_index=sequence_index,
            sequence_verified=sequence_verified,
            role=None if data.get("role") is None else str(data["role"]),
            created_at_utc=created_at,
        )

    @property
    def content_sha256(self) -> str:
        return sha256_text(self.content_text)

    def digest_payload(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "source_id": self.source_id,
            "source_record_key": self.source_record_key,
            "conversation_key": self.conversation_key,
            "sequence_index": self.sequence_index,
            "sequence_verified": self.sequence_verified,
            "role": self.role,
            "created_at_utc": self.created_at_utc,
            "content_text": self.content_text,
            "metadata": self.metadata,
        }

    @property
    def record_sha256(self) -> str:
        return digest_object(self.digest_payload())

    @property
    def metadata_json(self) -> str:
        return canonical_json(self.metadata)
