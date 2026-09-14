from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
from pathlib import Path

CHUNK_SIZE = 1024 * 1024


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(CHUNK_SIZE):
            h.update(chunk)
    return h.hexdigest()


def archive_file(source: Path, archive_dir: Path) -> dict[str, object]:
    """Copy a file byte-for-byte into a content-addressed archive.

    The source is never modified. The destination is named by SHA-256. If the
    same content already exists, it is verified and reused.
    """

    source = source.resolve(strict=True)
    if not source.is_file():
        raise ValueError(f"not a regular file: {source}")

    archive_dir.mkdir(parents=True, exist_ok=True)
    digest = sha256_file(source)
    suffix = "".join(source.suffixes)
    target = archive_dir / f"{digest}{suffix}"

    if target.exists():
        if sha256_file(target) != digest:
            raise RuntimeError(f"archive collision or corruption: {target}")
    else:
        temp = archive_dir / f".{target.name}.tmp-{os.getpid()}"
        try:
            with source.open("rb") as src, temp.open("xb") as dst:
                shutil.copyfileobj(src, dst, length=CHUNK_SIZE)
                dst.flush()
                os.fsync(dst.fileno())
            if sha256_file(temp) != digest:
                raise RuntimeError("copied file hash does not match source hash")
            os.replace(temp, target)
        finally:
            if temp.exists():
                temp.unlink()

    return {
        "source_path": str(source),
        "archive_path": str(target.resolve()),
        "sha256": digest,
        "size_bytes": source.stat().st_size,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Content-address a raw source without interpreting it.")
    parser.add_argument("source", type=Path)
    parser.add_argument("archive_dir", type=Path)
    args = parser.parse_args()
    print(json.dumps(archive_file(args.source, args.archive_dir), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
