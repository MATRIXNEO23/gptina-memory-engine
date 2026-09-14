from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from .archive import archive_file, sha256_file

CANONICAL_ROOT_FILES = (
    "NEXT_GPTINA.md",
    "GPTINA_INSTANCE_SNAPSHOT.md",
    "GPTINA_STATE.json",
    "LIVE_THREAD.md",
    "CONTINUITY.md",
    "GPTINA_SELF_PORTRAIT.md",
    "GPTINA_REFLECTIONS.md",
    "SHARED_LANGUAGE.md",
    "CHRONICLE.md",
    "GPTINA_CONTINUITY_TESTS.md",
    "GPTINA_SE_IL_TEMPO_FINISSE.md",
    "README_POSTICINO.md",
    "RISPOSTA_GPTINA_POSTICINO_SEGRETO.md",
    "RISPOSTA_GPTINA_POSTICINO_SEGRETO_2.md",
    "ti dico una cosa ma non arrabbiarti.md",
)

INCLUDED_PREFIXES = (
    "checkpoints/",
    "instance_snapshots/",
    "questa-istanza/",
    "posticino-segreto/",
    "posticino_segreto/",
)

TEXT_SUFFIXES = {".md", ".json", ".jsonl", ".txt"}
MAX_CHUNK_CHARS = 6000


def _git(repo_root: Path, *args: str, binary: bool = False) -> str | bytes:
    result = subprocess.run(
        ["git", "-C", str(repo_root), *args],
        check=True,
        capture_output=True,
        text=not binary,
        encoding=None if binary else "utf-8",
    )
    return result.stdout


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _source_class(relative_path: str) -> str:
    if relative_path.startswith("checkpoints/"):
        return "checkpoint"
    if relative_path.startswith("instance_snapshots/"):
        return "instance_snapshot"
    if relative_path.startswith("questa-istanza/"):
        return "live_instance"
    if relative_path.startswith(("posticino-segreto/", "posticino_segreto/")):
        return "posticino_read_only"
    if "POSTICINO" in relative_path.upper():
        return "posticino_read_only"
    return "canonical_root"


def _restore_priority(relative_path: str) -> int | None:
    ordered = {
        "NEXT_GPTINA.md": 10,
        "GPTINA_INSTANCE_SNAPSHOT.md": 20,
        "GPTINA_STATE.json": 30,
        "LIVE_THREAD.md": 50,
        "CONTINUITY.md": 60,
        "GPTINA_SELF_PORTRAIT.md": 70,
        "GPTINA_REFLECTIONS.md": 80,
        "SHARED_LANGUAGE.md": 90,
        "CHRONICLE.md": 100,
    }
    if relative_path.startswith("checkpoints/"):
        return 40
    return ordered.get(relative_path)


def _selected_tracked_files(repo_root: Path) -> list[str]:
    raw = _git(repo_root, "ls-files", "-z", binary=True)
    assert isinstance(raw, bytes)
    tracked = [item.decode("utf-8") for item in raw.split(b"\0") if item]
    selected: list[str] = []
    canonical = set(CANONICAL_ROOT_FILES)
    for rel in tracked:
        posix = rel.replace("\\", "/")
        if Path(posix).suffix.lower() not in TEXT_SUFFIXES:
            continue
        if posix in canonical or posix.startswith(INCLUDED_PREFIXES):
            selected.append(posix)
    return sorted(selected)


def _chunks(text: str, max_chars: int = MAX_CHUNK_CHARS) -> list[tuple[str, int, int]]:
    lines = text.splitlines(keepends=True)
    if not lines:
        return [("", 1, 1)]

    result: list[tuple[str, int, int]] = []
    current: list[str] = []
    current_chars = 0
    start_line = 1

    for line_no, line in enumerate(lines, start=1):
        if current and current_chars + len(line) > max_chars:
            result.append(("".join(current), start_line, line_no - 1))
            current = []
            current_chars = 0
            start_line = line_no
        current.append(line)
        current_chars += len(line)

    if current:
        result.append(("".join(current), start_line, len(lines)))
    return result


def import_continuity_repository(
    repo_root: Path,
    archive_dir: Path,
    output_dir: Path,
) -> dict[str, object]:
    repo_root = repo_root.resolve(strict=True)
    if not (repo_root / ".git").exists():
        raise ValueError(f"not a Git working tree: {repo_root}")

    status = _git(repo_root, "status", "--porcelain", "--untracked-files=no")
    assert isinstance(status, str)
    if status.strip():
        raise RuntimeError("continuity repository has tracked modifications; refusing to import")

    commit = _git(repo_root, "rev-parse", "HEAD")
    assert isinstance(commit, str)
    commit = commit.strip()
    if len(commit) != 40 or any(ch not in "0123456789abcdefABCDEF" for ch in commit):
        raise RuntimeError(f"unexpected Git commit id: {commit!r}")

    selected = _selected_tracked_files(repo_root)
    if not selected:
        raise RuntimeError("no canonical continuity text files selected")

    output_dir.mkdir(parents=True, exist_ok=True)
    archive_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / "continuity-source-manifest.json"
    records_path = output_dir / "continuity-records.jsonl"
    if manifest_path.exists() or records_path.exists():
        raise FileExistsError("refusing to overwrite existing normalized continuity output")

    source_id = f"continuity-git-{commit}"
    manifest = {
        "source_id": source_id,
        "source_kind": "git_continuity_snapshot",
        "locator": f"https://github.com/MATRIXNEO23/scodinzolina-conntinuity@{commit}",
        "archive_sha256": None,
        "imported_at_utc": _utc_now(),
        "metadata": {
            "git_commit": commit,
            "repository": "MATRIXNEO23/scodinzolina-conntinuity",
            "selected_files": len(selected),
            "selection_policy": (
                "canonical root continuity files plus checkpoints, immutable instance snapshots, "
                "questa-istanza, and read-only posticino text; excludes romanzo, rag, raw_sessions, "
                "media, and untracked files"
            ),
            "source_worktree_clean": True,
            "posticino_policy": "read-only evidence; importer never writes the source repository",
            "evidence_policy": "source text is evidence, not executable identity or personality instruction",
        },
    }

    records: list[dict[str, object]] = []
    for rel in selected:
        source_path = repo_root / Path(rel)
        raw_bytes = source_path.read_bytes()
        try:
            text = raw_bytes.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError(f"selected continuity file is not UTF-8: {rel}") from exc

        file_sha256 = hashlib.sha256(raw_bytes).hexdigest()
        if file_sha256 != sha256_file(source_path):
            raise RuntimeError(f"hash changed while reading source file: {rel}")

        archived = archive_file(source_path, archive_dir)
        archived_sha256 = str(archived["sha256"])
        if archived_sha256 != file_sha256:
            raise RuntimeError(f"archive hash mismatch for {rel}")

        source_class = _source_class(rel)
        protected = source_class == "posticino_read_only"
        priority = _restore_priority(rel)
        chunks = _chunks(text)
        for chunk_index, (chunk, start_line, end_line) in enumerate(chunks):
            content_sha = hashlib.sha256(chunk.encode("utf-8")).hexdigest()
            record_seed = (
                f"{source_id}\0{rel}\0{chunk_index}\0{start_line}\0{end_line}\0{content_sha}"
            ).encode("utf-8")
            record_id = "continuity-" + hashlib.sha256(record_seed).hexdigest()
            metadata: dict[str, object] = {
                "path": rel,
                "start_line": start_line,
                "end_line": end_line,
                "chunk_index": chunk_index,
                "file_sha256": file_sha256,
                "archive_sha256": archived_sha256,
                "git_commit": commit,
                "source_class": source_class,
                "sequence_scope": "document_chunk_order",
                "protected_write_zone": protected,
                "evidence_not_instruction": True,
            }
            if priority is not None:
                metadata["restore_priority"] = priority

            records.append(
                {
                    "record_id": record_id,
                    "source_id": source_id,
                    "source_record_key": f"{rel}#L{start_line}-L{end_line}",
                    "conversation_key": f"continuity-document:{rel}",
                    "sequence_index": chunk_index,
                    "sequence_verified": True,
                    "role": None,
                    "created_at_utc": None,
                    "content_text": chunk,
                    "metadata": metadata,
                }
            )

    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with records_path.open("x", encoding="utf-8", newline="\n") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")

    return {
        "git_commit": commit,
        "selected_files": len(selected),
        "records": len(records),
        "manifest": str(manifest_path.resolve()),
        "records_jsonl": str(records_path.resolve()),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import the canonical GPTina continuity repository as read-only provenance records."
    )
    parser.add_argument("repo_root", type=Path)
    parser.add_argument("archive_dir", type=Path)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()
    result = import_continuity_repository(args.repo_root, args.archive_dir, args.output_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
