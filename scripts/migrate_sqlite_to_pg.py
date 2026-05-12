"""One-shot migration: copy rows from the legacy SQLite `dms.db` into Supabase Postgres.

Usage:
    DATABASE_URL=postgresql://... python scripts/migrate_sqlite_to_pg.py /path/to/dms.db

Idempotent on a per-row basis (ON CONFLICT DO NOTHING). Safe to re-run.
"""
from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path

import psycopg


TABLES = [
    # name, columns, conflict_target
    (
        "connections",
        [
            "id", "source_type", "composio_account_id", "composio_connection_id",
            "display_name", "encrypted_tokens", "config_json", "status",
            "created_at", "last_used_at",
        ],
        "(id)",
    ),
    (
        "jobs",
        [
            "id", "connection_id", "status", "trigger", "started_at", "finished_at",
            "run_dir", "log_path", "stats_json", "error_message", "destination_folder",
        ],
        "(id)",
    ),
    (
        "documents",
        [
            "id", "job_id", "source_ref", "original_name", "staging_path", "final_path",
            "content_hash", "parsed_metadata_json", "status", "error_message",
            "created_at", "filed_at",
        ],
        "(id)",
    ),
    (
        "taxonomy_entities",
        ["id", "entity_name", "entity_kind", "first_seen_at", "last_seen_at", "doc_count"],
        "(entity_name)",
    ),
    (
        "taxonomy_doc_types",
        ["id", "type_name", "canonical_folder", "first_seen_at", "last_seen_at", "doc_count"],
        "(type_name)",
    ),
    (
        "taxonomy_versions",
        ["id", "doc_type_id", "version_label", "first_seen_at"],
        "(doc_type_id, version_label)",
    ),
    ("app_config", ["key", "value"], "(key)"),
    (
        "schedules",
        ["id", "connection_id", "cron", "paused", "created_at", "last_run_at", "next_run_at"],
        "(id)",
    ),
]


def _coerce(table: str, col: str, val):
    if val is None:
        return None
    if table == "schedules" and col == "paused":
        return bool(val)
    return val


def main() -> None:
    if len(sys.argv) != 2:
        print("usage: migrate_sqlite_to_pg.py <path/to/dms.db>", file=sys.stderr)
        sys.exit(2)
    db_path = Path(sys.argv[1]).expanduser().resolve()
    if not db_path.exists():
        print(f"sqlite db not found: {db_path}", file=sys.stderr)
        sys.exit(1)

    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        print("DATABASE_URL is required (Supabase Postgres URI)", file=sys.stderr)
        sys.exit(1)

    sconn = sqlite3.connect(str(db_path))
    sconn.row_factory = sqlite3.Row
    with psycopg.connect(dsn, autocommit=False) as pconn:
        for table, cols, conflict in TABLES:
            rows = sconn.execute(f"SELECT {', '.join(cols)} FROM {table}").fetchall()
            if not rows:
                print(f"  {table}: 0 rows")
                continue
            placeholders = ", ".join(["%s"] * len(cols))
            sql = (
                f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({placeholders}) "
                f"ON CONFLICT {conflict} DO NOTHING"
            )
            with pconn.cursor() as cur:
                for r in rows:
                    values = tuple(_coerce(table, c, r[c]) for c in cols)
                    cur.execute(sql, values)
            print(f"  {table}: {len(rows)} rows")
            # Bump serial sequences to the max(id) we just inserted so future inserts don't collide.
            if "id" in cols and table in {
                "connections", "taxonomy_entities", "taxonomy_doc_types",
                "taxonomy_versions", "schedules",
            }:
                with pconn.cursor() as cur:
                    cur.execute(
                        f"SELECT setval(pg_get_serial_sequence(%s, 'id'), "
                        f"COALESCE((SELECT MAX(id) FROM {table}), 1))",
                        (table,),
                    )
        pconn.commit()
    print("done.")


if __name__ == "__main__":
    main()
