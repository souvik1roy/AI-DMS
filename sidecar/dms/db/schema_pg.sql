-- Postgres schema for AI DMS. Mirrors the prior SQLite shape so application
-- code (column names, value types, semantics) stays unchanged.
--
-- Timestamps are epoch-milliseconds stored as BIGINT to avoid touching the
-- many sites that compute `int(time.time() * 1000)` in Python.

CREATE TABLE IF NOT EXISTS connections (
    id                       BIGSERIAL PRIMARY KEY,
    source_type              TEXT     NOT NULL,
    composio_account_id      TEXT,
    composio_connection_id   TEXT,
    display_name             TEXT     NOT NULL,
    encrypted_tokens         BYTEA,
    config_json              TEXT,
    status                   TEXT     NOT NULL DEFAULT 'active',
    created_at               BIGINT   NOT NULL,
    last_used_at             BIGINT
);

CREATE TABLE IF NOT EXISTS jobs (
    id                  TEXT     PRIMARY KEY,
    connection_id       BIGINT   REFERENCES connections(id),
    status              TEXT     NOT NULL,
    trigger             TEXT     NOT NULL,
    started_at          BIGINT   NOT NULL,
    finished_at         BIGINT,
    run_dir             TEXT     NOT NULL,
    log_path            TEXT     NOT NULL,
    stats_json          TEXT,
    error_message       TEXT,
    destination_folder  TEXT
);
CREATE INDEX IF NOT EXISTS idx_jobs_status  ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_started ON jobs(started_at DESC);

CREATE TABLE IF NOT EXISTS documents (
    id                     TEXT     PRIMARY KEY,
    job_id                 TEXT     NOT NULL REFERENCES jobs(id),
    source_ref             TEXT,
    original_name          TEXT     NOT NULL,
    staging_path           TEXT,
    final_path             TEXT,
    content_hash           TEXT,
    parsed_metadata_json   TEXT,
    status                 TEXT     NOT NULL,
    error_message          TEXT,
    created_at             BIGINT   NOT NULL,
    filed_at               BIGINT,
    UNIQUE(content_hash, job_id)
);
CREATE INDEX IF NOT EXISTS idx_docs_job  ON documents(job_id);
CREATE INDEX IF NOT EXISTS idx_docs_hash ON documents(content_hash);

CREATE TABLE IF NOT EXISTS taxonomy_entities (
    id              BIGSERIAL PRIMARY KEY,
    entity_name     TEXT     NOT NULL UNIQUE,
    entity_kind     TEXT,
    first_seen_at   BIGINT   NOT NULL,
    last_seen_at    BIGINT   NOT NULL,
    doc_count       BIGINT   NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS taxonomy_doc_types (
    id                BIGSERIAL PRIMARY KEY,
    type_name         TEXT     NOT NULL UNIQUE,
    canonical_folder  TEXT     NOT NULL,
    first_seen_at     BIGINT   NOT NULL,
    last_seen_at      BIGINT   NOT NULL,
    doc_count         BIGINT   NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS taxonomy_versions (
    id              BIGSERIAL PRIMARY KEY,
    doc_type_id     BIGINT   NOT NULL REFERENCES taxonomy_doc_types(id),
    version_label   TEXT     NOT NULL,
    first_seen_at   BIGINT   NOT NULL,
    UNIQUE(doc_type_id, version_label)
);

CREATE TABLE IF NOT EXISTS app_config (
    key    TEXT PRIMARY KEY,
    value  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS schedules (
    id              BIGSERIAL PRIMARY KEY,
    connection_id   BIGINT   NOT NULL REFERENCES connections(id) ON DELETE CASCADE,
    cron            TEXT     NOT NULL,
    paused          BOOLEAN  NOT NULL DEFAULT FALSE,
    created_at      BIGINT   NOT NULL,
    last_run_at     BIGINT,
    next_run_at     BIGINT
);
CREATE INDEX IF NOT EXISTS idx_schedules_connection ON schedules(connection_id);
