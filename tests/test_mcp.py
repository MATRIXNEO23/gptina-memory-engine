from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from mcp import Client

from gptina_memory_engine.builder import build_database
from gptina_memory_engine.server import create_server


class MCPContractTests(unittest.IsolatedAsyncioTestCase):
    async def test_server_exposes_only_read_tools(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = root / "manifest.json"
            records = root / "records.jsonl"
            db = root / "memory.sqlite3"

            manifest.write_text(
                json.dumps(
                    {
                        "source_id": "mcp-synthetic",
                        "source_kind": "synthetic_fixture",
                        "locator": "tests/test_mcp.py",
                        "archive_sha256": None,
                        "imported_at_utc": "2026-09-14T05:00:00Z",
                        "metadata": {"fixture": True},
                    }
                ),
                encoding="utf-8",
            )
            records.write_text(
                json.dumps(
                    {
                        "record_id": "m1",
                        "source_id": "mcp-synthetic",
                        "content_text": "synthetic memory",
                        "metadata": {},
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            build_database(manifest, records, db)

            server = create_server(db)
            async with Client(server) as client:
                result = await client.list_tools()
                names = {tool.name for tool in result.tools}

            self.assertEqual(
                names,
                {
                    "memory_status",
                    "search_memory",
                    "find_exact",
                    "get_record",
                    "get_context",
                    "get_timeline",
                    "get_source_info",
                },
            )


if __name__ == "__main__":
    unittest.main()
