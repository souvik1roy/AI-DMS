"""Source-agnostic staging helpers.

In the web build documents arrive via HTTP upload (and, in time, Composio
connectors that download from Gmail/Drive/OneDrive). Both paths share the
same staging contract: stream bytes into the `staging` bucket under
`<job_id>/<doc_id>_<safe_original_name>`, then hand a `StagedDoc` to the
orchestrator. The orchestrator never touches a local filesystem.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from dms.config import STAGING_BUCKET, SUPPORTED_EXTS
from dms.storage import supabase_store

_UNSAFE_NAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


def sanitize_filename(name: str) -> str:
    """Collapse anything not alnum/dot/underscore/dash into '_' and clip length."""
    cleaned = _UNSAFE_NAME_RE.sub("_", name).strip("._")
    return cleaned[:160] or "unnamed"


def suffix_of(name: str) -> str:
    """Return the lowercase extension of `name` (e.g. '.pdf'); empty string if none."""
    idx = name.rfind(".")
    if idx < 0:
        return ""
    return name[idx:].lower()


def is_supported(name: str) -> bool:
    return suffix_of(name) in SUPPORTED_EXTS


@dataclass(frozen=True)
class StagedDoc:
    doc_id: str
    original_name: str
    source_ref: str
    staging_key: str
    content_hash: str
    size_bytes: int
    suffix: str


def stage_bytes(
    *,
    data: bytes,
    original_name: str,
    job_id: str,
    doc_id: str,
    source_ref: str | None = None,
    content_type: str = "application/octet-stream",
) -> StagedDoc:
    """Upload `data` to the staging bucket under <job_id>/<doc_id>_<safe>.

    Returns a `StagedDoc` carrying the bucket key plus the SHA-256 hash and size
    (both computed in-memory before upload).
    """
    safe = sanitize_filename(original_name)
    key = f"{job_id}/{doc_id}_{safe}"
    supabase_store.upload(STAGING_BUCKET, key, data, content_type=content_type)
    digest = hashlib.sha256(data).hexdigest()
    return StagedDoc(
        doc_id=doc_id,
        original_name=original_name,
        source_ref=source_ref or key,
        staging_key=key,
        content_hash=digest,
        size_bytes=len(data),
        suffix=suffix_of(original_name),
    )
