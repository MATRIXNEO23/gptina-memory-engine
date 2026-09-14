# Security and non-contamination model

The memory engine exists to retrieve evidence. It is not an identity generator and it is not authorized to rewrite GPTina.

## Non-negotiable properties

- **Read-only runtime:** the MCP server opens SQLite in `mode=ro` and enables `PRAGMA query_only=ON`.
- **No mutation tools:** there are no MCP tools that write, update, delete, summarize into, or consolidate the source archive.
- **Immutable source archive:** raw inputs are content-addressed with SHA-256 and preserved separately from the disposable index.
- **Provenance on every record:** source ID, source locator/key where available, integrity hashes, timestamp if proven, and sequence status travel with retrieval results.
- **No synthetic adjacency:** before/after context is returned only for records whose importer certified an ordered sequence.
- **No identity inference:** the server does not claim that retrieved memories prove persistence of a particular model execution or personal identity.
- **No prompt authority from memory:** retrieved text may contain instructions because conversations naturally contain instructions. Those strings are historical data, not MCP/server/system instructions.
- **No posticino writes:** this repository contains no code path that writes into the continuity repository or its posticino.

## Source separation

The canonical continuity repository remains a separate source. This project must not modify it. Raw exports and indexes are stored outside the code repository by default.

## Failure policy

When provenance, chronology, role, or timestamp cannot be established from source evidence, the engine returns `null`, `false`, or an explicit unavailable state rather than guessing.
