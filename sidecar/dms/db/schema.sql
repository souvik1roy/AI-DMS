PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS connections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_type TEXT NOT NULL,
    composio_account_id TEXT,
    composio_connection_id TEXT,
    display_name TEXT NOT NULL,
    encrypted_tokens BLOB,
    config_json TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    created_at INTEGER NOT NULL,
    last_used_at INTEGER
);

CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    connection_id INTEGER REFERENCES connections(id),
    status TEXT NOT NULL,
    trigger TEXT NOT NULL,
    started_at INTEGER NOT NULL,
    finished_at INTEGER,
    run_dir TEXT NOT NULL,
    log_path TEXT NOT NULL,
    stats_json TEXT,
    error_message TEXT,
    destination_folder TEXT
);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_started ON jobs(started_at DESC);

CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL REFERENCES jobs(id),
    source_ref TEXT,
    original_name TEXT NOT NULL,
    staging_path TEXT,
    final_path TEXT,
    content_hash TEXT,
    parsed_metadata_json TEXT,
    status TEXT NOT NULL,
    error_message TEXT,
    created_at INTEGER NOT NULL,
    filed_at INTEGER,
    UNIQUE(content_hash, job_id)
);
CREATE INDEX IF NOT EXISTS idx_docs_job ON documents(job_id);
CREATE INDEX IF NOT EXISTS idx_docs_hash ON documents(content_hash);

CREATE TABLE IF NOT EXISTS taxonomy_entities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_name TEXT NOT NULL UNIQUE,
    entity_kind TEXT,
    first_seen_at INTEGER NOT NULL,
    last_seen_at INTEGER NOT NULL,
    doc_count INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS taxonomy_doc_types (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type_name TEXT NOT NULL UNIQUE,
    canonical_folder TEXT NOT NULL,
    first_seen_at INTEGER NOT NULL,
    last_seen_at INTEGER NOT NULL,
    doc_count INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS taxonomy_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_type_id INTEGER NOT NULL REFERENCES taxonomy_doc_types(id),
    version_label TEXT NOT NULL,
    first_seen_at INTEGER NOT NULL,
    UNIQUE(doc_type_id, version_label)
);

CREATE TABLE IF NOT EXISTS app_config (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS schedules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    connection_id INTEGER NOT NULL REFERENCES connections(id) ON DELETE CASCADE,
    cron TEXT NOT NULL,
    paused INTEGER NOT NULL DEFAULT 0,
    created_at INTEGER NOT NULL,
    last_run_at INTEGER,
    next_run_at INTEGER
);
CREATE INDEX IF NOT EXISTS idx_schedules_connection ON schedules(connection_id);
