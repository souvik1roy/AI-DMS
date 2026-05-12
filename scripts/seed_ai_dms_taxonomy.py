"""Pre-seed the AI-DMS bucket with one top-level folder per allowed document
type. Idempotent: re-running it is a no-op for types whose `.keep` already
exists.

Usage:
    DATABASE_URL=...  SUPABASE_URL=...  SUPABASE_SERVICE_ROLE_KEY=... \
        sidecar/.venv/bin/python scripts/seed_ai_dms_taxonomy.py
"""
from __future__ import annotations

import sys

from dms.config import ORGANIZED_BUCKET
from dms.llm.prompts import ALLOWED_DOCUMENT_TYPES
from dms.pipeline.filer import _sanitize_segment
from dms.storage import supabase_store


def main() -> None:
    created = 0
    existed = 0
    failed: list[tuple[str, str]] = []
    for type_name in ALLOWED_DOCUMENT_TYPES:
        folder = _sanitize_segment(type_name)
        key = f"{folder}/.keep"
        try:
            if supabase_store.exists(ORGANIZED_BUCKET, key):
                existed += 1
                continue
            supabase_store.upload(
                ORGANIZED_BUCKET,
                key,
                b"# Marker so the folder is visible in Browse before any docs land here.\n",
                content_type="text/plain",
            )
            created += 1
        except Exception as e:  # noqa: BLE001
            failed.append((type_name, str(e)))

    print(f"seeded {created} new folders · {existed} already present")
    if failed:
        print(f"{len(failed)} failures:")
        for t, msg in failed:
            print(f"  {t}: {msg}")
        sys.exit(1)


if __name__ == "__main__":
    main()
