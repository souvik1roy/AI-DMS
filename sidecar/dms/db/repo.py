from __future__ import annotations

import json
import logging
import threading
import time
from contextlib import contextmanager
from importlib import resources
from typing import Any, Iterator

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from dms.config import DATABASE_URL


log = logging.getLogger("dms.db")


def _now() -> int:
    return int(time.time() * 1000)


_pool: ConnectionPool | None = None
_pool_lock = threading.Lock()


def _get_pool() -> ConnectionPool:
    global _pool
    if _pool is not None:
        return _pool
    with _pool_lock:
        if _pool is not None:
            return _pool
        if not DATABASE_URL:
            raise RuntimeError("DATABASE_URL is not set; cannot open Postgres pool")
        _pool = ConnectionPool(
            conninfo=DATABASE_URL,
            min_size=1,
            max_size=10,
            kwargs={"row_factory": dict_row},
        )
        _pool.wait()
        return _pool


def init_schema_once() -> None:
    """Apply schema_pg.sql in an idempotent way (`CREATE TABLE IF NOT EXISTS …`)."""
    sql = resources.files("dms.db").joinpath("schema_pg.sql").read_text(encoding="utf-8")
    pool = _get_pool()
    with pool.connection() as c:
        with c.cursor() as cur:
            cur.execute(sql)
        c.commit()


class Repo:
    def __init__(self, *_: Any, **__: Any) -> None:
        # Positional / keyword args are accepted for back-compat with the older
        # `Repo(db_path)` signature; they're ignored now (we read DATABASE_URL).
        init_schema_once()

    @contextmanager
    def conn(self) -> Iterator[psycopg.Connection]:
        pool = _get_pool()
        with pool.connection() as c:
            yield c

    # ---------- jobs ----------

    def insert_job(
        self,
        job_id: str,
        connection_id: int | None,
        run_dir: Any,
        log_path: Any,
        trigger: str = "manual",
        destination_folder: str | None = None,
    ) -> None:
        with self.conn() as c:
            c.execute(
                """
                INSERT INTO jobs
                    (id, connection_id, status, trigger, started_at, run_dir, log_path,
                     destination_folder)
                VALUES (%s, %s, 'pending', %s, %s, %s, %s, %s)
                """,
                (
                    job_id,
                    connection_id,
                    trigger,
                    _now(),
                    str(run_dir),
                    str(log_path),
                    destination_folder,
                ),
            )
            c.commit()

    def update_job_status(
        self,
        job_id: str,
        status: str,
        *,
        stats: dict[str, Any] | None = None,
        error: str | None = None,
        finished: bool = False,
    ) -> None:
        with self.conn() as c:
            c.execute(
                """
                UPDATE jobs
                   SET status = %s,
                       stats_json = COALESCE(%s, stats_json),
                       error_message = COALESCE(%s, error_message),
                       finished_at = CASE WHEN %s THEN %s ELSE finished_at END
                 WHERE id = %s
                """,
                (
                    status,
                    json.dumps(stats) if stats is not None else None,
                    error,
                    finished,
                    _now() if finished else None,
                    job_id,
                ),
            )
            c.commit()

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        with self.conn() as c:
            row = c.execute("SELECT * FROM jobs WHERE id = %s", (job_id,)).fetchone()
            return dict(row) if row else None

    def list_jobs(self, limit: int = 50) -> list[dict[str, Any]]:
        with self.conn() as c:
            rows = c.execute(
                "SELECT * FROM jobs ORDER BY started_at DESC LIMIT %s", (limit,)
            ).fetchall()
            return [dict(r) for r in rows]

    # ---------- documents ----------

    def insert_document(
        self,
        doc_id: str,
        job_id: str,
        original_name: str,
        staging_path: Any,
        source_ref: str | None,
    ) -> None:
        with self.conn() as c:
            c.execute(
                """
                INSERT INTO documents
                    (id, job_id, source_ref, original_name, staging_path, status, created_at)
                VALUES (%s, %s, %s, %s, %s, 'fetched', %s)
                """,
                (doc_id, job_id, source_ref, original_name, str(staging_path), _now()),
            )
            c.commit()

    def set_document_hash(self, doc_id: str, content_hash: str) -> None:
        with self.conn() as c:
            c.execute(
                "UPDATE documents SET content_hash = %s WHERE id = %s",
                (content_hash, doc_id),
            )
            c.commit()

    def has_hash_in_other_job(self, content_hash: str, job_id: str) -> bool:
        with self.conn() as c:
            row = c.execute(
                """
                SELECT 1 FROM documents
                 WHERE content_hash = %s AND job_id != %s AND status = 'filed'
                 LIMIT 1
                """,
                (content_hash, job_id),
            ).fetchone()
            return row is not None

    def set_document_parsed(self, doc_id: str, metadata: dict[str, Any]) -> None:
        with self.conn() as c:
            c.execute(
                """
                UPDATE documents
                   SET parsed_metadata_json = %s,
                       status = 'parsed'
                 WHERE id = %s
                """,
                (json.dumps(metadata), doc_id),
            )
            c.commit()

    def set_document_filed(self, doc_id: str, final_path: Any) -> None:
        with self.conn() as c:
            c.execute(
                """
                UPDATE documents
                   SET final_path = %s,
                       staging_path = NULL,
                       status = 'filed',
                       filed_at = %s
                 WHERE id = %s
                """,
                (str(final_path), _now(), doc_id),
            )
            c.commit()

    def set_document_skipped(self, doc_id: str, reason: str) -> None:
        with self.conn() as c:
            c.execute(
                "UPDATE documents SET status = 'skipped_duplicate', error_message = %s WHERE id = %s",
                (reason, doc_id),
            )
            c.commit()

    def set_document_failed(self, doc_id: str, error: str) -> None:
        with self.conn() as c:
            c.execute(
                "UPDATE documents SET status = 'failed', error_message = %s WHERE id = %s",
                (error, doc_id),
            )
            c.commit()

    def list_documents_for_job(self, job_id: str) -> list[dict[str, Any]]:
        with self.conn() as c:
            rows = c.execute(
                "SELECT * FROM documents WHERE job_id = %s ORDER BY created_at",
                (job_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_document(self, doc_id: str) -> dict[str, Any] | None:
        with self.conn() as c:
            row = c.execute("SELECT * FROM documents WHERE id = %s", (doc_id,)).fetchone()
            return dict(row) if row else None

    def dashboard_stats(self) -> dict[str, Any]:
        """Aggregated metrics for the Dashboard landing tab. Four queries in
        one pool checkout — typically returns in <50 ms against Supabase.
        """
        week_ago = _now() - 7 * 86_400_000
        with self.conn() as c:
            total = c.execute(
                "SELECT COUNT(*) AS n FROM documents WHERE status='filed'"
            ).fetchone()["n"]
            this_week = c.execute(
                "SELECT COUNT(*) AS n FROM documents "
                "WHERE status='filed' AND filed_at >= %s",
                (week_ago,),
            ).fetchone()["n"]
            prev_week = c.execute(
                "SELECT COUNT(*) AS n FROM documents "
                "WHERE status='filed' AND filed_at >= %s AND filed_at < %s",
                (week_ago - 7 * 86_400_000, week_ago),
            ).fetchone()["n"]
            top_types = c.execute(
                """
                SELECT (parsed_metadata_json::json->>'document_type') AS type,
                       COUNT(*) AS count
                  FROM documents
                 WHERE status='filed'
                   AND parsed_metadata_json IS NOT NULL
                   AND (parsed_metadata_json::json->>'document_type') IS NOT NULL
                 GROUP BY (parsed_metadata_json::json->>'document_type')
                 ORDER BY count DESC
                 LIMIT 8
                """
            ).fetchall()
            top_entities = c.execute(
                """
                SELECT (parsed_metadata_json::json->>'entity_name') AS entity,
                       COUNT(*) AS count
                  FROM documents
                 WHERE status='filed'
                   AND parsed_metadata_json IS NOT NULL
                   AND (parsed_metadata_json::json->>'entity_name') IS NOT NULL
                   AND (parsed_metadata_json::json->>'entity_name') <> ''
                 GROUP BY (parsed_metadata_json::json->>'entity_name')
                 ORDER BY count DESC
                 LIMIT 8
                """
            ).fetchall()
            modality_rows = c.execute(
                """
                SELECT COALESCE(parsed_metadata_json::json->>'modality', 'image') AS modality,
                       COUNT(*) AS count
                  FROM documents
                 WHERE status='filed'
                   AND parsed_metadata_json IS NOT NULL
                 GROUP BY COALESCE(parsed_metadata_json::json->>'modality', 'image')
                 ORDER BY count DESC
                """
            ).fetchall()
            recent = c.execute(
                """
                SELECT id, original_name, final_path, parsed_metadata_json,
                       filed_at, job_id
                  FROM documents
                 WHERE status='filed'
                 ORDER BY filed_at DESC NULLS LAST
                 LIMIT 10
                """
            ).fetchall()
            types_used = c.execute(
                """
                SELECT COUNT(DISTINCT parsed_metadata_json::json->>'document_type') AS n
                  FROM documents WHERE status='filed'
                """
            ).fetchone()["n"]
            entities_used = c.execute(
                """
                SELECT COUNT(DISTINCT parsed_metadata_json::json->>'entity_name') AS n
                  FROM documents WHERE status='filed'
                """
            ).fetchone()["n"]
        return {
            "total_documents": int(total or 0),
            "filed_this_week": int(this_week or 0),
            "filed_prev_week": int(prev_week or 0),
            "types_used": int(types_used or 0),
            "entities_used": int(entities_used or 0),
            "top_types": [
                {"type": r["type"], "count": int(r["count"])} for r in top_types
            ],
            "top_entities": [
                {"entity": r["entity"], "count": int(r["count"])} for r in top_entities
            ],
            "modality_breakdown": [
                {"modality": r["modality"] or "image", "count": int(r["count"])}
                for r in modality_rows
            ],
            "recent_uploads": [dict(r) for r in recent],
        }

    def get_documents_by_final_paths(self, keys: list[str]) -> dict[str, dict[str, Any]]:
        """Bulk-fetch documents whose `final_path` is in `keys`. Returns a map
        keyed by final_path so the Browse tab can attach parsed metadata.
        """
        if not keys:
            return {}
        with self.conn() as c:
            rows = c.execute(
                "SELECT * FROM documents WHERE final_path = ANY(%s)",
                (keys,),
            ).fetchall()
            return {dict(r)["final_path"]: dict(r) for r in rows}

    def delete_job(self, job_id: str) -> None:
        """Remove the job row and all its document rows. Storage cleanup is the
        caller's job — this is DB-only.
        """
        with self.conn() as c:
            c.execute("DELETE FROM documents WHERE job_id = %s", (job_id,))
            c.execute("DELETE FROM jobs WHERE id = %s", (job_id,))
            c.commit()

    # ---------- taxonomy ----------

    def upsert_entity(self, name: str, kind: str | None = None) -> None:
        with self.conn() as c:
            c.execute(
                """
                INSERT INTO taxonomy_entities
                    (entity_name, entity_kind, first_seen_at, last_seen_at, doc_count)
                VALUES (%s, %s, %s, %s, 1)
                ON CONFLICT(entity_name) DO UPDATE SET
                    last_seen_at = EXCLUDED.last_seen_at,
                    doc_count = taxonomy_entities.doc_count + 1
                """,
                (name, kind, _now(), _now()),
            )
            c.commit()

    def upsert_doc_type(self, type_name: str, canonical_folder: str) -> int:
        with self.conn() as c:
            c.execute(
                """
                INSERT INTO taxonomy_doc_types
                    (type_name, canonical_folder, first_seen_at, last_seen_at, doc_count)
                VALUES (%s, %s, %s, %s, 1)
                ON CONFLICT(type_name) DO UPDATE SET
                    last_seen_at = EXCLUDED.last_seen_at,
                    doc_count = taxonomy_doc_types.doc_count + 1
                """,
                (type_name, canonical_folder, _now(), _now()),
            )
            row = c.execute(
                "SELECT id FROM taxonomy_doc_types WHERE type_name = %s", (type_name,)
            ).fetchone()
            c.commit()
            return int(row["id"])

    def upsert_version(self, doc_type_id: int, version_label: str) -> None:
        with self.conn() as c:
            c.execute(
                """
                INSERT INTO taxonomy_versions (doc_type_id, version_label, first_seen_at)
                VALUES (%s, %s, %s)
                ON CONFLICT(doc_type_id, version_label) DO NOTHING
                """,
                (doc_type_id, version_label, _now()),
            )
            c.commit()

    def snapshot_taxonomy(self) -> dict[str, Any]:
        with self.conn() as c:
            entities = [
                dict(r)
                for r in c.execute(
                    "SELECT entity_name, entity_kind FROM taxonomy_entities"
                ).fetchall()
            ]
            doc_types = [
                dict(r)
                for r in c.execute(
                    "SELECT id, type_name, canonical_folder FROM taxonomy_doc_types"
                ).fetchall()
            ]
            versions = [
                dict(r)
                for r in c.execute(
                    """
                    SELECT t.type_name AS document_type, v.version_label
                      FROM taxonomy_versions v
                      JOIN taxonomy_doc_types t ON t.id = v.doc_type_id
                    """
                ).fetchall()
            ]
        return {
            "entities": [e["entity_name"] for e in entities],
            "document_types": [
                {"name": d["type_name"], "canonical_folder": d["canonical_folder"]}
                for d in doc_types
            ],
            "versions": versions,
        }

    # ---------- connections ----------

    def insert_connection(
        self,
        source_type: str,
        display_name: str,
        composio_connection_id: str | None,
        composio_account_id: str | None,
        config_json: str | None = None,
    ) -> int:
        with self.conn() as c:
            row = c.execute(
                """
                INSERT INTO connections
                    (source_type, composio_account_id, composio_connection_id,
                     display_name, config_json, status, created_at)
                VALUES (%s, %s, %s, %s, %s, 'active', %s)
                RETURNING id
                """,
                (
                    source_type,
                    composio_account_id,
                    composio_connection_id,
                    display_name,
                    config_json,
                    _now(),
                ),
            ).fetchone()
            c.commit()
            return int(row["id"])

    def list_connections(self) -> list[dict[str, Any]]:
        with self.conn() as c:
            rows = c.execute(
                """
                SELECT id, source_type, composio_account_id, composio_connection_id,
                       display_name, config_json, status, created_at, last_used_at
                  FROM connections
                 ORDER BY created_at DESC
                """
            ).fetchall()
            return [dict(r) for r in rows]

    def get_connection(self, connection_id: int) -> dict[str, Any] | None:
        with self.conn() as c:
            row = c.execute(
                "SELECT * FROM connections WHERE id = %s", (connection_id,)
            ).fetchone()
            return dict(row) if row else None

    def mark_connection_used(self, connection_id: int) -> None:
        with self.conn() as c:
            c.execute(
                "UPDATE connections SET last_used_at = %s WHERE id = %s",
                (_now(), connection_id),
            )
            c.commit()

    def update_connection_status(self, connection_id: int, status: str) -> None:
        with self.conn() as c:
            c.execute(
                "UPDATE connections SET status = %s WHERE id = %s",
                (status, connection_id),
            )
            c.commit()

    def delete_connection(self, connection_id: int) -> None:
        with self.conn() as c:
            c.execute("DELETE FROM connections WHERE id = %s", (connection_id,))
            c.commit()

    # ---------- schedules ----------

    def insert_schedule(self, connection_id: int, cron: str) -> int:
        with self.conn() as c:
            row = c.execute(
                """
                INSERT INTO schedules (connection_id, cron, paused, created_at)
                VALUES (%s, %s, FALSE, %s)
                RETURNING id
                """,
                (connection_id, cron, _now()),
            ).fetchone()
            c.commit()
            return int(row["id"])

    def list_schedules(self) -> list[dict[str, Any]]:
        with self.conn() as c:
            rows = c.execute(
                """
                SELECT s.*, c.display_name, c.source_type
                  FROM schedules s
                  JOIN connections c ON c.id = s.connection_id
                 ORDER BY s.created_at DESC
                """
            ).fetchall()
            return [dict(r) for r in rows]

    def get_schedule(self, schedule_id: int) -> dict[str, Any] | None:
        with self.conn() as c:
            row = c.execute(
                "SELECT * FROM schedules WHERE id = %s", (schedule_id,)
            ).fetchone()
            return dict(row) if row else None

    def set_schedule_paused(self, schedule_id: int, paused: bool) -> None:
        with self.conn() as c:
            c.execute(
                "UPDATE schedules SET paused = %s WHERE id = %s",
                (paused, schedule_id),
            )
            c.commit()

    def set_schedule_next_run(self, schedule_id: int, next_run_at: int | None) -> None:
        with self.conn() as c:
            c.execute(
                "UPDATE schedules SET next_run_at = %s WHERE id = %s",
                (next_run_at, schedule_id),
            )
            c.commit()

    def mark_schedule_ran(self, schedule_id: int) -> None:
        with self.conn() as c:
            c.execute(
                "UPDATE schedules SET last_run_at = %s WHERE id = %s",
                (_now(), schedule_id),
            )
            c.commit()

    def delete_schedule(self, schedule_id: int) -> None:
        with self.conn() as c:
            c.execute("DELETE FROM schedules WHERE id = %s", (schedule_id,))
            c.commit()

    # ---------- app config ----------

    def set_config(self, key: str, value: str) -> None:
        with self.conn() as c:
            c.execute(
                """
                INSERT INTO app_config (key, value) VALUES (%s, %s)
                ON CONFLICT(key) DO UPDATE SET value = EXCLUDED.value
                """,
                (key, value),
            )
            c.commit()

    def get_config(self, key: str) -> str | None:
        with self.conn() as c:
            row = c.execute(
                "SELECT value FROM app_config WHERE key = %s", (key,)
            ).fetchone()
            return row["value"] if row else None

    def delete_config(self, key: str) -> None:
        with self.conn() as c:
            c.execute("DELETE FROM app_config WHERE key = %s", (key,))
            c.commit()
