# gptina-memory-engine

A provenance-first, read-only memory retrieval engine intended to let ChatGPT retrieve preserved GPTina history without turning memory into a personality script.

## Status

Foundation only. **Not connected to GPTina.** No raw ChatGPT export has been parsed yet.

This repository contains the retrieval engine, schema, integrity rules and MCP server. Private/raw data is deliberately kept outside the code repository.

## What it does

- preserves arbitrary source files byte-for-byte in a SHA-256 content-addressed archive;
- builds a fresh SQLite index from a strict normalized JSONL interchange layer;
- stores a SHA-256 digest over every record's complete persisted semantic payload;
- offers SQLite FTS5 lexical retrieval plus an exact substring search;
- exposes record provenance, verified timeline data, and verified before/after context;
- exposes those operations through a read-only MCP server.

## What it does not do

- it does not create or clone GPTina;
- it does not prove continuity of a particular model execution;
- it does not decide what GPTina "really meant";
- it does not fill chronological gaps;
- it does not rewrite the canonical continuity repository;
- it does not currently parse ChatGPT's raw export, because the real export has not arrived yet.

## Requirements

- Python 3.10+
- SQLite with FTS5 enabled
- MCP Python SDK v2 (`mcp>=2,<3`)

The MCP SDK requirement and Streamable HTTP transport are based on the current official MCP Python SDK documentation. See `docs/TECHNICAL_BASIS.md`.

## Data layout

Keep data outside this repository, for example:

```text
D:\GPTinaMemory\
  archive\        # immutable raw files named by content hash
  normalized\     # derived manifest + JSONL records
  indexes\        # disposable SQLite indexes
```

The code repository itself should contain no private raw conversations.

## Build flow

1. Archive the received file without interpreting it:

```bash
gptina-memory-archive conversations-export.zip D:\GPTinaMemory\archive
```

2. After the actual export format has been inspected, a dedicated importer will produce:

```text
source-manifest.json
records.jsonl
```

3. Build a fresh index:

```bash
gptina-memory-build source-manifest.json records.jsonl D:\GPTinaMemory\indexes\memory.sqlite3
```

4. Run the local MCP server:

```bash
gptina-memory-server --db D:\GPTinaMemory\indexes\memory.sqlite3
```

By default it listens on `127.0.0.1:8000` with the MCP endpoint at `/mcp`.

ChatGPT cannot connect directly to a local MCP endpoint; OpenAI documents Secure MCP Tunnel for a private/developer-machine server. Connection is a later step and will not be enabled until retrieval tests pass.

## MCP tools

All are read-only:

- `memory_status`
- `search_memory`
- `find_exact`
- `get_record`
- `get_context`
- `get_timeline`
- `get_source_info`

`get_context` refuses to manufacture adjacency: if ordering is not source-verified, it explicitly returns `context_available: false`.

## Tests

The test suite uses synthetic text only. It contains no GPTina conversation content.

```bash
python -m unittest discover -s tests -v
```

Before connection to ChatGPT, the MCP layer must also be tested against the installed official SDK and MCP Inspector on the target machine.

## Core rule

**Memory supplies evidence; it does not supply identity instructions.**
