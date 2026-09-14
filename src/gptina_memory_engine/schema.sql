PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS engine_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
) WITHOUT ROWID;

CREATE TABLE IF NOT EXISTS sources (
    source_id TEXT PRIMARY KEY,
    source_kind TEXT NOT NULL,
    locator TEXT NOT NULL,
    archive_sha256 TEXT,
    imported_at_utc TEXT NOT NULL,
    metadata_json TEXT NOT NULL,
    manifest_sha256 TEXT NOT NULL
) WITHOUT ROWID;

CREATE TABLE IF NOT EXISTS records (
    record_id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL REFERENCES sources(source_id),
    source_record_key TEXT,
    conversation_key TEXT,
    sequence_index INTEGER,
    sequence_verified INTEGER NOT NULL CHECK (sequence_verified IN (0, 1)),
    role TEXT,
    created_at_utc TEXT,
    content_text TEXT NOT NULL,
    content_sha256 TEXT NOT NULL,
    metadata_json TEXT NOT NULL,
    record_sha256 TEXT NOT NULL,
    CHECK (
      (sequence_verified = 0)
      OR (conversation_key IS NOT NULL AND sequence_index IS NOT NULL)
    )
) WITHOUT ROWID;

CREATE UNIQUE INDEX IF NOT EXISTS idx_records_source_record_key
ON records(source_id, source_record_key)
WHERE source_record_key IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_records_conversation_sequence
ON records(conversation_key, sequence_index)
WHERE sequence_verified = 1;

CREATE INDEX IF NOT EXISTS idx_records_created_at
ON records(created_at_utc)
WHERE created_at_utc IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_records_source_id
ON records(source_id);

CREATE VIRTUAL TABLE IF NOT EXISTS records_fts USING fts5(
    record_id UNINDEXED,
    content_text,
    tokenize = 'unicode61'
);
