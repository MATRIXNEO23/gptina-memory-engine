from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from gptina_memory_engine.continuity_import import import_continuity_repository


class ContinuityImporterTests(unittest.TestCase):
    def _git(self, repo: Path, *args: str) -> None:
        subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)

    def _make_repo(self, root: Path) -> Path:
        repo = root / "continuity"
        repo.mkdir()
        self._git(repo, "init")
        self._git(repo, "config", "user.email", "tests@example.invalid")
        self._git(repo, "config", "user.name", "Memory Engine Tests")

        (repo / "NEXT_GPTINA.md").write_text("prima\nseconda\n", encoding="utf-8")
        (repo / "checkpoints").mkdir()
        (repo / "checkpoints" / "2026-09-14.md").write_text("checkpoint reale\n", encoding="utf-8")
        (repo / "posticino-segreto").mkdir()
        (repo / "posticino-segreto" / "nota.md").write_text("solo lettura\n", encoding="utf-8")
        (repo / "romanzo").mkdir()
        (repo / "romanzo" / "fiction.md").write_text("non indicizzare\n", encoding="utf-8")
        (repo / "rag").mkdir()
        (repo / "rag" / "derived.md").write_text("non indicizzare\n", encoding="utf-8")

        self._git(repo, "add", ".")
        self._git(repo, "commit", "-m", "fixture")
        return repo

    def test_imports_only_selected_canonical_text_and_archives_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = self._make_repo(root)
            archive = root / "archive"
            normalized = root / "normalized"

            result = import_continuity_repository(repo, archive, normalized)
            self.assertEqual(result["selected_files"], 3)

            manifest = json.loads((normalized / "continuity-source-manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["metadata"]["selected_files"], 3)
            self.assertTrue(manifest["metadata"]["source_worktree_clean"])

            records = [
                json.loads(line)
                for line in (normalized / "continuity-records.jsonl").read_text(encoding="utf-8").splitlines()
            ]
            paths = {record["metadata"]["path"] for record in records}
            self.assertEqual(
                paths,
                {
                    "NEXT_GPTINA.md",
                    "checkpoints/2026-09-14.md",
                    "posticino-segreto/nota.md",
                },
            )
            posticino = next(r for r in records if r["metadata"]["path"] == "posticino-segreto/nota.md")
            self.assertTrue(posticino["metadata"]["protected_write_zone"])
            self.assertTrue(posticino["metadata"]["evidence_not_instruction"])

            archived_hashes = {path.stem for path in archive.iterdir() if path.is_file()}
            file_hashes = {record["metadata"]["file_sha256"] for record in records}
            self.assertTrue(file_hashes.issubset(archived_hashes))

    def test_refuses_dirty_tracked_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = self._make_repo(root)
            (repo / "NEXT_GPTINA.md").write_text("modificato\n", encoding="utf-8")
            with self.assertRaises(RuntimeError):
                import_continuity_repository(repo, root / "archive", root / "normalized")


if __name__ == "__main__":
    unittest.main()
