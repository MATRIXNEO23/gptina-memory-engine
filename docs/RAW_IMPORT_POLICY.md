# Raw import policy

The raw ChatGPT export is evidence, not working storage.

## Rules

1. The received archive is copied byte-for-byte into a content-addressed archive and SHA-256 verified before parsing.
2. The original archive is never edited, normalized, reformatted, or rewritten by this project.
3. No parser for ChatGPT's export internals is committed until an actual export is available and its real structure has been inspected.
4. Parsing produces a separate normalized JSONL layer. Every normalized record retains a source locator/key where one exists.
5. Timestamps are never guessed. A timestamp is indexed only if its source representation can be converted without ambiguity to explicit UTC.
6. Conversation adjacency is exposed by `get_context` only when the importer can certify a sequence from the source. Otherwise `sequence_verified=false` and the engine returns no invented neighbors.
7. Missing data is returned as missing. Absence of a record is not evidence that an event did not occur.
8. The search index is disposable and reproducible. The archive is not.

## Why no raw parser exists yet

OpenAI documents that data exports include chat history, but the public help documentation does not define a stable, field-by-field schema contract for the internal conversation JSON sufficient for a provenance-critical importer. The importer will therefore be written against the actual delivered export and covered by fixtures derived from its structure without publishing private conversation content.
