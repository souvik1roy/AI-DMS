"""Taxonomy helpers used in the type-first filing pipeline.

The old reasoner-driven `apply_taxonomy_additions` / `load_taxonomy_snapshot`
flow is gone — paths are now derived directly from vision metadata and
`filer.compute_final_key`. This module keeps only the small folder-name
slugger that the migration script and a few legacy call sites still use.
"""
from __future__ import annotations

import re


_FOLDER_RE = re.compile(r"[^A-Za-z0-9 _.\-&]+")


def slugify_folder(name: str) -> str:
    """Make a string safe for use as a folder segment without losing readability."""
    cleaned = _FOLDER_RE.sub(" ", name).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned[:80] or "Unknown"
