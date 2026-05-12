"""Thin wrapper around the Supabase Storage REST API.

We talk to Storage over HTTPS using the project URL + service-role key — the
sidecar is the only writer, so RLS doesn't apply here. Public read access is
never granted; the UI gets short-lived signed URLs through `/documents/{id}/signed_url`.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterable

import httpx

from dms.config import (
    SIGNED_URL_TTL_SECONDS,
    SUPABASE_SERVICE_ROLE_KEY,
    SUPABASE_URL,
)

log = logging.getLogger("dms.storage")


class StorageError(RuntimeError):
    pass


def _require_config() -> tuple[str, str]:
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        raise StorageError(
            "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set "
            "(sidecar cannot talk to Supabase Storage without them)"
        )
    return SUPABASE_URL.rstrip("/"), SUPABASE_SERVICE_ROLE_KEY


def _headers(token: str, content_type: str | None = None) -> dict[str, str]:
    h = {
        "Authorization": f"Bearer {token}",
        "apikey": token,
    }
    if content_type:
        h["Content-Type"] = content_type
    return h


def _normalize_key(key: str) -> str:
    return key.lstrip("/")


def upload(
    bucket: str,
    key: str,
    data: bytes | Path,
    *,
    content_type: str = "application/octet-stream",
    upsert: bool = True,
) -> str:
    """Upload bytes (or a file at `data`) to bucket/key. Returns the stored key."""
    url, token = _require_config()
    key = _normalize_key(key)
    payload = data.read_bytes() if isinstance(data, Path) else data
    headers = _headers(token, content_type)
    if upsert:
        headers["x-upsert"] = "true"
    r = httpx.post(
        f"{url}/storage/v1/object/{bucket}/{key}",
        headers=headers,
        content=payload,
        timeout=60.0,
    )
    if r.status_code == 409 and not upsert:
        raise StorageError(f"object already exists: {bucket}/{key}")
    if r.status_code >= 300:
        raise StorageError(f"upload {bucket}/{key} failed: {r.status_code} {r.text}")
    return key


def download(bucket: str, key: str) -> bytes:
    url, token = _require_config()
    key = _normalize_key(key)
    r = httpx.get(
        f"{url}/storage/v1/object/{bucket}/{key}",
        headers=_headers(token),
        timeout=60.0,
    )
    if r.status_code >= 300:
        raise StorageError(f"download {bucket}/{key} failed: {r.status_code} {r.text}")
    return r.content


def exists(bucket: str, key: str) -> bool:
    """Return True if an object exists at bucket/key."""
    url, token = _require_config()
    key = _normalize_key(key)
    parent, _, name = key.rpartition("/")
    prefix = parent
    r = httpx.post(
        f"{url}/storage/v1/object/list/{bucket}",
        headers=_headers(token, "application/json"),
        json={"prefix": prefix, "limit": 1000, "search": name},
        timeout=30.0,
    )
    if r.status_code >= 300:
        return False
    for entry in r.json() or []:
        if entry.get("name") == name:
            return True
    return False


def signed_url(bucket: str, key: str, expires: int = SIGNED_URL_TTL_SECONDS) -> str:
    url, token = _require_config()
    key = _normalize_key(key)
    r = httpx.post(
        f"{url}/storage/v1/object/sign/{bucket}/{key}",
        headers=_headers(token, "application/json"),
        json={"expiresIn": expires},
        timeout=30.0,
    )
    if r.status_code >= 300:
        raise StorageError(f"sign {bucket}/{key} failed: {r.status_code} {r.text}")
    body = r.json()
    signed = body.get("signedURL") or body.get("signedUrl")
    if not signed:
        raise StorageError(f"sign {bucket}/{key} returned no URL: {body}")
    if signed.startswith("/"):
        signed = f"{url}/storage/v1{signed}"
    return signed


def delete(bucket: str, keys: str | Iterable[str]) -> int:
    """Delete one or many objects. Returns the number deleted."""
    url, token = _require_config()
    if isinstance(keys, str):
        key_list = [_normalize_key(keys)]
    else:
        key_list = [_normalize_key(k) for k in keys]
    if not key_list:
        return 0
    r = httpx.request(
        "DELETE",
        f"{url}/storage/v1/object/{bucket}",
        headers=_headers(token, "application/json"),
        json={"prefixes": key_list},
        timeout=30.0,
    )
    if r.status_code >= 300:
        raise StorageError(f"delete {bucket} failed: {r.status_code} {r.text}")
    try:
        return len(r.json() or [])
    except ValueError:
        return len(key_list)


def list_children(bucket: str, prefix: str = "", limit: int = 1000) -> list[dict]:
    """List the immediate folder/file children of `prefix` inside `bucket`.

    Each returned entry is one of:
      {"name": str, "is_folder": True}                  for sub-prefixes
      {"name": str, "is_folder": False, "size": int,
       "updated_at": str, "content_type": str | None}   for files
    """
    url, token = _require_config()
    prefix = _normalize_key(prefix).rstrip("/")
    entries: list[dict] = []
    offset = 0
    page = min(max(limit, 1), 1000)
    while True:
        r = httpx.post(
            f"{url}/storage/v1/object/list/{bucket}",
            headers=_headers(token, "application/json"),
            json={
                "prefix": prefix,
                "limit": page,
                "offset": offset,
                "sortBy": {"column": "name", "order": "asc"},
            },
            timeout=30.0,
        )
        if r.status_code >= 300:
            raise StorageError(
                f"list {bucket}/{prefix} failed: {r.status_code} {r.text}"
            )
        batch = r.json() or []
        for e in batch:
            name = e.get("name")
            if not name:
                continue
            # Supabase marks sub-prefixes with id == None and no metadata.
            is_folder = e.get("id") is None and not e.get("metadata")
            if is_folder:
                entries.append({"name": name, "is_folder": True})
            else:
                meta = e.get("metadata") or {}
                entries.append(
                    {
                        "name": name,
                        "is_folder": False,
                        "size": meta.get("size"),
                        "updated_at": e.get("updated_at"),
                        "content_type": meta.get("mimetype"),
                    }
                )
        if len(batch) < page:
            break
        offset += page
        if offset >= limit:
            break
    return entries


def delete_prefix(bucket: str, prefix: str) -> int:
    """Delete every object whose key starts with `prefix/`. Returns count deleted."""
    url, token = _require_config()
    prefix = _normalize_key(prefix).rstrip("/")
    total = 0
    offset = 0
    page = 100
    while True:
        r = httpx.post(
            f"{url}/storage/v1/object/list/{bucket}",
            headers=_headers(token, "application/json"),
            json={"prefix": prefix, "limit": page, "offset": offset},
            timeout=30.0,
        )
        if r.status_code >= 300:
            raise StorageError(f"list {bucket}/{prefix} failed: {r.status_code} {r.text}")
        entries = r.json() or []
        if not entries:
            break
        keys = [f"{prefix}/{e['name']}" for e in entries if e.get("name")]
        if keys:
            total += delete(bucket, keys)
        if len(entries) < page:
            break
        offset += page
    return total
