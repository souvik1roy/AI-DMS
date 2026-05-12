"""Move filed documents from the legacy per-job prefix layout
(`OrganiseAI_<job_id>/<Entity>/<DocType>/[<Version>/]<Year>/<file>`) to the
new type-first layout (`<DocumentType>/<EntityOrPerson>/<file>`).

Idempotent: rows whose `final_path` already matches the new shape are skipped.
The script reads parsed metadata from Postgres and uses
`filer.compute_final_key` so the path logic stays in lock-step with the live
pipeline.

Usage:
    DATABASE_URL=...  SUPABASE_URL=...  SUPABASE_SERVICE_ROLE_KEY=... \
        sidecar/.venv/bin/python scripts/migrate_to_type_first_schema.py
"""
from __future__ import annotations

import json
import sys

from dms.config import ORGANIZED_BUCKET
from dms.db.repo import Repo
from dms.pipeline.filer import (
    clear_folder_cache,
    compute_final_key,
    sha256_bytes,
)
from dms.storage import supabase_store


def _looks_new_shape(key: str) -> bool:
    """Heuristic: new shape has exactly 2 separators (TYPE/ENTITY/FILE). The
    legacy shape always starts with `OrganiseAI_` and has 3+ segments before
    the filename.
    """
    if key.startswith("OrganiseAI_"):
        return False
    parts = [p for p in key.split("/") if p]
    return len(parts) == 3


def main() -> None:
    repo = Repo()
    rows: list[dict] = []
    with repo.conn() as c:
        rows = [
            dict(r)
            for r in c.execute(
                "SELECT id, original_name, final_path, parsed_metadata_json "
                "FROM documents WHERE status = 'filed' AND final_path IS NOT NULL"
            ).fetchall()
        ]

    print(f"found {len(rows)} filed documents")
    clear_folder_cache()

    migrated = 0
    skipped = 0
    failed: list[tuple[str, str]] = []
    for r in rows:
        doc_id = r["id"]
        old_key = r["final_path"]
        if _looks_new_shape(old_key):
            skipped += 1
            continue
        meta_raw = r.get("parsed_metadata_json")
        meta: dict = {}
        if meta_raw:
            try:
                meta = json.loads(meta_raw)
            except (TypeError, ValueError):
                meta = {}
        try:
            body = supabase_store.download(ORGANIZED_BUCKET, old_key)
            old_hash = sha256_bytes(body)
            _, _, new_key = compute_final_key(
                document_type=meta.get("document_type"),
                entity_name=meta.get("entity_name"),
                person_name=meta.get("person_name"),
                original_name=r["original_name"] or meta.get("original_name") or "unnamed",
            )
            if new_key == old_key:
                skipped += 1
                continue
            supabase_store.upload(ORGANIZED_BUCKET, new_key, body)
            written = supabase_store.download(ORGANIZED_BUCKET, new_key)
            if sha256_bytes(written) != old_hash:
                supabase_store.delete(ORGANIZED_BUCKET, new_key)
                raise RuntimeError("hash mismatch after copy")
            with repo.conn() as c:
                c.execute(
                    "UPDATE documents SET final_path = %s WHERE id = %s",
                    (new_key, doc_id),
                )
                c.commit()
            supabase_store.delete(ORGANIZED_BUCKET, old_key)
            migrated += 1
            print(f"  {old_key}  ->  {new_key}")
        except Exception as e:  # noqa: BLE001
            failed.append((old_key, str(e)))

    clear_folder_cache()
    print(f"migrated {migrated} · skipped {skipped} · failed {len(failed)}")
    if failed:
        for k, msg in failed:
            print(f"  FAIL {k}: {msg}")
        sys.exit(1)


if __name__ == "__main__":
    main()
