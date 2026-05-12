from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path


# ---- Storage / DB configuration (env-driven) ---------------------------------

# Supabase buckets the sidecar reads/writes.
STAGING_BUCKET = os.environ.get("DMS_STAGING_BUCKET", "staging")
ORGANIZED_BUCKET = os.environ.get("DMS_ORGANIZED_BUCKET", "organized")

# Postgres connection string. Required at runtime; the migration script and
# psycopg pool both read it directly.
DATABASE_URL = os.environ.get("DATABASE_URL", "")

# Supabase project URL + service role key for Storage operations.
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

# Settings key for the user-configurable global destination prefix (bucket key prefix).
APP_CONFIG_DESTINATION_ROOT = "destination_root"

# Default key prefix when neither a per-run override nor a global default is set.
DEFAULT_DESTINATION_PATTERN = "OrganiseAI_{job_id}"


def default_destination_for_job(job_id: str) -> str:
    return DEFAULT_DESTINATION_PATTERN.format(job_id=job_id)


def resolve_destination(
    *,
    requested: str | None,
    global_default: str | None,
    job_id: str,
) -> str:
    """Pick the destination key prefix for a job:

      1. explicit per-run override
      2. user-configured global default
      3. auto-default `OrganiseAI_<job_id>`
    """
    if requested:
        return requested.strip("/")
    if global_default:
        return global_default.strip("/")
    return default_destination_for_job(job_id)


@dataclass(frozen=True)
class Paths:
    """Surface that callers expect. In the web build everything lives in Supabase
    Storage, so most fields are bucket/prefix strings (or a single shared tmpdir
    used for ephemeral PDF page renders that we then upload).
    """

    staging_bucket: str
    organized_bucket: str
    tmp_dir: Path

    # Legacy fields kept so callers and the /paths API surface keep working.
    app_data: Path
    local_data: Path
    runs_dir: Path
    engine_dir: Path
    organized_root: Path
    logs_dir: Path
    job_logs_dir: Path
    db_path: Path
    taxonomy_json: Path

    @classmethod
    def resolve(cls) -> "Paths":
        tmp = Path(os.environ.get("DMS_TMP_DIR") or tempfile.gettempdir()) / "ai-dms"
        runs = tmp / "runs"
        logs = tmp / "logs"
        for d in (tmp, runs, logs, logs / "jobs"):
            d.mkdir(parents=True, exist_ok=True)
        return cls(
            staging_bucket=STAGING_BUCKET,
            organized_bucket=ORGANIZED_BUCKET,
            tmp_dir=tmp,
            app_data=tmp,
            local_data=tmp,
            runs_dir=runs,
            engine_dir=tmp,
            organized_root=Path(f"supabase://{ORGANIZED_BUCKET}"),
            logs_dir=logs,
            job_logs_dir=logs / "jobs",
            db_path=tmp / "_unused.db",
            taxonomy_json=tmp / "taxonomy.json",
        )


# Supported document file extensions. Grouped here so the dispatcher in
# pipeline/extractors.py and the UI's drag-drop both stay in lock-step.
IMAGE_EXTS = frozenset({".jpg", ".jpeg", ".png", ".heic", ".tiff", ".tif", ".webp", ".gif"})
PDF_EXTS = frozenset({".pdf"})
OFFICE_EXTS = frozenset({".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".odt", ".ods", ".odp"})
TEXT_EXTS = frozenset({".csv", ".tsv", ".txt"})
AUDIO_EXTS = frozenset({".mp3", ".wav", ".m4a", ".ogg", ".flac", ".aac"})
VIDEO_EXTS = frozenset({".mp4", ".mov", ".mkv", ".webm", ".avi"})
SUPPORTED_EXTS = (
    IMAGE_EXTS | PDF_EXTS | OFFICE_EXTS | TEXT_EXTS | AUDIO_EXTS | VIDEO_EXTS
)

# Vision parse render DPI.
PAGE_RENDER_DPI = 200

# Reasoning model parameters (legacy — reasoner is no longer called).
REASONER_TEMPERATURE = 0.2

# Confidence threshold below which the pipeline renders extra pages.
LOW_CONFIDENCE_THRESHOLD = 0.6

# OpenAI model selection (env-overridable).
OPENAI_VISION_MODEL = os.environ.get("OPENAI_VISION_MODEL", "gpt-4o")
OPENAI_REASONER_MODEL = os.environ.get("OPENAI_REASONER_MODEL", "gpt-4o")
OPENAI_TEXT_MODEL = os.environ.get("OPENAI_TEXT_MODEL", "gpt-4o")
OPENAI_STT_MODEL = os.environ.get("OPENAI_STT_MODEL", "gpt-4o-transcribe")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

# Signed URL TTL (seconds) for in-pipeline calls and UI links.
SIGNED_URL_TTL_SECONDS = int(os.environ.get("DMS_SIGNED_URL_TTL", "3600"))

# System-binary locations (auto-detect if empty).
LIBREOFFICE_BIN = os.environ.get("LIBREOFFICE_BIN", "")
FFMPEG_BIN = os.environ.get("FFMPEG_BIN", "ffmpeg")

# Audio/video trim length before transcription.
AUDIO_TRIM_SECONDS = int(os.environ.get("DMS_AUDIO_TRIM_SECONDS", "60"))

# Office conversion timeout — first LibreOffice invocation in a fresh container
# can take ~6 s (font cache); subsequent runs are 1–2 s.
LIBREOFFICE_TIMEOUT_SECONDS = int(os.environ.get("DMS_LIBREOFFICE_TIMEOUT", "120"))
