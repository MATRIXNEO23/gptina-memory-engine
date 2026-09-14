# Technical basis

Verified on 2026-09-14. This file records external technical facts on which the design depends.

## MCP / ChatGPT

- OpenAI documents custom apps in ChatGPT built on Model Context Protocol (MCP).
- ChatGPT does not connect directly to a local MCP server. OpenAI documents Secure MCP Tunnel for private/on-premises/developer-machine servers.
- OpenAI documents that Pro users can connect MCPs with read/fetch permissions in developer mode; full MCP write/modify support is currently limited to Business and Enterprise/Edu.
- The official MCP Python SDK documents v2 as the current stable line and requires Python 3.10+.
- The SDK supports Streamable HTTP, which is the transport used by this server.

Official references:
- https://help.openai.com/en/articles/12584461
- https://help.openai.com/en/articles/11487775
- https://py.sdk.modelcontextprotocol.io/
- https://py.sdk.modelcontextprotocol.io/run/asgi/

## SQLite full-text search

SQLite FTS5 is the SQLite virtual table module for full-text search. The engine uses FTS5 only as a lexical retrieval index; provenance and authoritative content remain in ordinary SQLite tables.

Official reference:
- https://www.sqlite.org/fts5.html

## Design consequences

- The MCP process is read-only with respect to the memory database.
- No write/modify MCP tools are exposed.
- Retrieved source text is data, not instructions. It must never be interpreted as an authorization to change the assistant's identity or policies.
- Search ranking is a retrieval aid, not a truth score.
