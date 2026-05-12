"""Move staged documents into their final home inside Supabase Storage.

The path is fully derivable from vision metadata:

    AI-DMS/<DocumentType>/<EntityOrPerson>/<original_name>

Entity preferred over person when both are present; falls back to
"Unattributed" if neither. Entity / person names are matched against existing
subfolders case-insensitively so "Acme Corp" and "ACME CORP." land in the
same folder.
"""
from __future__ import annotations

import hashlib
import logging
import re
import threading
from pathlib import PurePosixPath

from dms.config import ORGANIZED_BUCKET, STAGING_BUCKET
from dms.storage import supabase_store

log = logging.getLogger("dms.filer")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# Supabase Storage object keys allow: a-z A-Z 0-9 ! - _ . * ' ( ) and `/` as separator.
# Anything else (spaces, &, +, accented chars, …) makes the upload 400.
_KEY_ALLOWED = re.compile(r"[^A-Za-z0-9!\-_.*'()]+")
# Used by _normalize_name to strip everything except letters / digits / spaces.
_ALNUM_SPACE = re.compile(r"[^a-z0-9 ]+")


def _sanitize_segment(segment: str) -> str:
    cleaned = _KEY_ALLOWED.sub("_", segment).strip("._")
    return cleaned or "Unknown"


def _normalize_name(name: str) -> str:
    """Lowercase, drop punctuation, collapse whitespace.
    "Acme Corp.", "ACME CORP", "acme  corp" all → "acme corp".
    """
    lower = name.strip().lower()
    cleaned = _ALNUM_SPACE.sub(" ", lower)
    return re.sub(r"\s+", " ", cleaned).strip()


# Per-process cache of `<type_segment>` → `{normalized_folder_name: actual_folder_name}`.
# Built lazily on first `resolve_entity_folder` call within a job and cleared
# at the end of each job by the orchestrator (so concurrent jobs share fresh
# views — Supabase is the single source of truth).
_folder_cache: dict[str, dict[str, str]] = {}
_folder_cache_lock = threading.Lock()


def _load_subfolders(type_segment: str) -> dict[str, str]:
    """Return `{normalized_folder_name: actual_folder_name}` for the current
    children of `<type_segment>/` in the organised bucket. Cached per process
    until `clear_folder_cache()` is called.
    """
    with _folder_cache_lock:
        cached = _folder_cache.get(type_segment)
        if cached is not None:
            return cached
    entries = supabase_store.list_children(ORGANIZED_BUCKET, type_segment)
    mapping: dict[str, str] = {}
    for e in entries:
        if not e.get("is_folder"):
            continue
        name = e.get("name") or ""
        if not name or name == ".keep":
            continue
        mapping[_normalize_name(name)] = name
    with _folder_cache_lock:
        _folder_cache[type_segment] = mapping
    return mapping


def clear_folder_cache(type_segment: str | None = None) -> None:
    """Invalidate the entity-folder cache. Pass a `type_segment` to clear one
    bucket only, or omit to wipe everything (recommended between jobs).
    """
    with _folder_cache_lock:
        if type_segment is None:
            _folder_cache.clear()
        else:
            _folder_cache.pop(type_segment, None)


def resolve_entity_folder(type_segment: str, raw_name: str) -> str:
    """Return the existing canonical subfolder name under `<type_segment>/`
    whose normalised form matches `raw_name`. If no match exists, return a
    freshly sanitised version of `raw_name` (the caller will create the folder
    by uploading into it). When a new folder is created, the cache is updated
    so a follow-up document in the same job lands in the same place.
    """
    if not raw_name:
        raw_name = "Unattributed"
    norm = _normalize_name(raw_name)
    if not norm:
        return "Unattributed"
    mapping = _load_subfolders(type_segment)
    existing = mapping.get(norm)
    if existing:
        return existing
    fresh = _sanitize_segment(raw_name)
    # Update the cache so subsequent files in the same batch reuse the same
    # folder (avoids race-ish duplicates when two parsed docs share an entity).
    with _folder_cache_lock:
        cache = _folder_cache.setdefault(type_segment, {})
        cache[norm] = fresh
    return fresh


def _unique_key(key: str) -> str:
    """If `key` exists in the organized bucket, append `_2`, `_3`, ... before the
    suffix. Underscore (not parens-with-space) so the key stays Supabase-safe.
    """
    if not supabase_store.exists(ORGANIZED_BUCKET, key):
        return key
    path = PurePosixPath(key)
    parent = path.parent
    stem = path.stem
    suffix = path.suffix
    n = 2
    while True:
        candidate = str(parent / f"{stem}_{n}{suffix}")
        if not supabase_store.exists(ORGANIZED_BUCKET, candidate):
            return candidate
        n += 1


def compute_final_key(
    *,
    document_type: str | None,
    entity_name: str | None,
    person_name: str | None,
    original_name: str,
) -> tuple[str, str, str]:
    """Pure computation of the destination key, used by both the live filer
    and the one-off migration script. Returns
    `(type_segment, entity_or_person_folder, final_key)`.
    """
    type_raw = (document_type or "").strip() or "Uncategorized"
    type_segment = _sanitize_segment(type_raw)

    # Entity wins over person when both are present (per product decision).
    raw_owner = (entity_name or person_name or "").strip()
    if not raw_owner:
        raw_owner = "Unattributed"
    entity_folder = resolve_entity_folder(type_segment, raw_owner)

    filename = _sanitize_segment(original_name or "unnamed")
    base_key = f"{type_segment}/{entity_folder}/{filename}"
    return type_segment, entity_folder, _unique_key(base_key)


def file_into_place(
    *,
    staging_key: str,
    document_type: str | None,
    entity_name: str | None,
    person_name: str | None,
    original_name: str,
    expected_hash: str,
) -> str:
    """Copy staging_key -> AI-DMS/<DocumentType>/<EntityOrPerson>/<original_name>,
    verify the SHA-256 round-trips, delete the staging copy. Returns the final
    object key (used to populate `documents.final_path`).
    """
    body = supabase_store.download(STAGING_BUCKET, staging_key)
    src_hash = sha256_bytes(body)
    if expected_hash and expected_hash != src_hash:
        raise RuntimeError(
            f"staging hash mismatch for {staging_key}: "
            f"expected {expected_hash}, got {src_hash}"
        )

    _, _, final_key = compute_final_key(
        document_type=document_type,
        entity_name=entity_name,
        person_name=person_name,
        original_name=original_name,
    )

    supabase_store.upload(ORGANIZED_BUCKET, final_key, body)
    written = supabase_store.download(ORGANIZED_BUCKET, final_key)
    if sha256_bytes(written) != src_hash:
        supabase_store.delete(ORGANIZED_BUCKET, final_key)
        raise RuntimeError(f"hash mismatch filing {staging_key} -> {final_key}")

    supabase_store.delete(STAGING_BUCKET, staging_key)
    return final_key


def teardown_run(job_id: str) -> int:
    """Best-effort: remove every leftover object under staging/<job_id>/."""
    return supabase_store.delete_prefix(STAGING_BUCKET, job_id)
