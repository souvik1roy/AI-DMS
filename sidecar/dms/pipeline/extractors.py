"""Modality-aware extractor: given a staged file's bytes + extension, produce
an `ExtractedInput` the classifier can act on.

Two output shapes:
  - `image`: signed URLs to one or two rendered PNGs (PDF + image inputs +
    Office files converted via LibreOffice).
  - `text`:  a string excerpt of the extracted content (CSV / TSV / TXT +
    audio / video transcripts produced via ffmpeg + OpenAI STT).

The audio / video / text extractors also return `transcript_full`, which the
orchestrator uploads as a sidecar `.transcript.txt` alongside the source
file in the AI-DMS bucket.
"""
from __future__ import annotations

import csv
import io
import logging
from dataclasses import dataclass, field
from typing import Literal

from dms.config import (
    AUDIO_EXTS,
    IMAGE_EXTS,
    OFFICE_EXTS,
    PDF_EXTS,
    SIGNED_URL_TTL_SECONDS,
    STAGING_BUCKET,
    TEXT_EXTS,
    VIDEO_EXTS,
)
from dms.pipeline.office import office_to_pdf
from dms.pipeline.pdf_pages import render_first_and_last
from dms.pipeline.transcribe import transcribe, trim_to_audio_mp3
from dms.storage import supabase_store

log = logging.getLogger("dms.extractors")


@dataclass(frozen=True)
class ExtractedInput:
    modality: Literal["image", "text"]
    image_urls: list[str] = field(default_factory=list)
    text_excerpt: str = ""
    # Bytes to persist as `<final_key>.transcript.txt` alongside the source.
    transcript_full: bytes | None = None
    # Short note on which extraction path ran (good for the parse log + UI).
    extraction_note: str = ""


# Hard caps so the classifier prompt never balloons.
_TEXT_EXCERPT_BYTES = 6 * 1024
_CSV_SAMPLE_ROWS = 50


# ---------- image-mode extractors -----------------------------------------


def _upload_page(
    *, key: str, body: bytes, content_type: str
) -> str:
    supabase_store.upload(STAGING_BUCKET, key, body, content_type=content_type)
    return supabase_store.signed_url(STAGING_BUCKET, key, SIGNED_URL_TTL_SECONDS)


def _extract_from_pdf_or_image_bytes(
    *, body: bytes, suffix: str, job_id: str, doc_id: str, note: str
) -> ExtractedInput:
    rendered = render_first_and_last(body, suffix)
    # Passthrough image: keep its original extension on the staging key so
    # content-type sniffers see something familiar.
    if suffix in IMAGE_EXTS and rendered.last_bytes is None:
        first_key = f"{job_id}/pages/{doc_id}_first{suffix}"
    else:
        first_key = f"{job_id}/pages/{doc_id}_first.png"
    urls = [
        _upload_page(
            key=first_key,
            body=rendered.first_bytes,
            content_type=rendered.image_content_type,
        )
    ]
    if rendered.last_bytes is not None:
        last_key = f"{job_id}/pages/{doc_id}_last.png"
        urls.append(
            _upload_page(
                key=last_key,
                body=rendered.last_bytes,
                content_type=rendered.image_content_type,
            )
        )
    return ExtractedInput(modality="image", image_urls=urls, extraction_note=note)


def _extract_image_native(body: bytes, suffix: str, job_id: str, doc_id: str) -> ExtractedInput:
    return _extract_from_pdf_or_image_bytes(
        body=body, suffix=suffix, job_id=job_id, doc_id=doc_id,
        note="image-passthrough" if suffix in IMAGE_EXTS else "pdf-native",
    )


def _extract_office(body: bytes, suffix: str, job_id: str, doc_id: str) -> ExtractedInput:
    pdf_bytes = office_to_pdf(body, suffix)
    return _extract_from_pdf_or_image_bytes(
        body=pdf_bytes, suffix=".pdf", job_id=job_id, doc_id=doc_id,
        note=f"office-via-libreoffice ({suffix})",
    )


# ---------- text-mode extractors ------------------------------------------


def _decode_text(body: bytes) -> str:
    for enc in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            return body.decode(enc)
        except UnicodeDecodeError:
            continue
    return body.decode("utf-8", errors="replace")


def _truncate(text: str, limit: int = _TEXT_EXCERPT_BYTES) -> str:
    if len(text.encode("utf-8")) <= limit:
        return text
    out = text.encode("utf-8")[:limit]
    return out.decode("utf-8", errors="ignore") + "\n…[truncated]"


def _extract_csv_like(body: bytes, delimiter: str) -> ExtractedInput:
    text = _decode_text(body)
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    rows: list[str] = []
    for i, row in enumerate(reader):
        rows.append("\t".join(row))
        if i >= _CSV_SAMPLE_ROWS:
            break
    excerpt = "\n".join(rows)
    return ExtractedInput(
        modality="text",
        text_excerpt=_truncate(excerpt),
        transcript_full=text.encode("utf-8"),
        extraction_note="csv" if delimiter == "," else "tsv",
    )


def _extract_text(body: bytes, suffix: str, job_id: str, doc_id: str) -> ExtractedInput:
    if suffix == ".csv":
        return _extract_csv_like(body, delimiter=",")
    if suffix == ".tsv":
        return _extract_csv_like(body, delimiter="\t")
    # .txt
    text = _decode_text(body)
    return ExtractedInput(
        modality="text",
        text_excerpt=_truncate(text),
        transcript_full=text.encode("utf-8"),
        extraction_note="txt",
    )


# ---------- audio / video extractors --------------------------------------


def _extract_audio(body: bytes, suffix: str, job_id: str, doc_id: str) -> ExtractedInput:
    mp3 = trim_to_audio_mp3(body)
    transcript = transcribe(mp3, filename_hint=f"clip{suffix}.mp3")
    return ExtractedInput(
        modality="text",
        text_excerpt=_truncate(transcript) or "(silent / unintelligible audio)",
        transcript_full=transcript.encode("utf-8"),
        extraction_note=f"audio-transcribed ({suffix})",
    )


def _extract_video(body: bytes, suffix: str, job_id: str, doc_id: str) -> ExtractedInput:
    # ffmpeg strips video automatically because trim_to_audio_mp3 passes -vn.
    mp3 = trim_to_audio_mp3(body)
    transcript = transcribe(mp3, filename_hint=f"clip{suffix}.mp3")
    return ExtractedInput(
        modality="text",
        text_excerpt=_truncate(transcript) or "(silent video — audio track empty)",
        transcript_full=transcript.encode("utf-8"),
        extraction_note=f"video-audio-transcribed ({suffix})",
    )


# ---------- dispatcher ----------------------------------------------------


def extract(
    *, body: bytes, suffix: str, job_id: str, doc_id: str
) -> ExtractedInput:
    """Route the file's bytes to the right extractor based on its extension."""
    suffix = (suffix or "").lower()
    if suffix in PDF_EXTS or suffix in IMAGE_EXTS:
        return _extract_image_native(body, suffix, job_id, doc_id)
    if suffix in OFFICE_EXTS:
        return _extract_office(body, suffix, job_id, doc_id)
    if suffix in TEXT_EXTS:
        return _extract_text(body, suffix, job_id, doc_id)
    if suffix in AUDIO_EXTS:
        return _extract_audio(body, suffix, job_id, doc_id)
    if suffix in VIDEO_EXTS:
        return _extract_video(body, suffix, job_id, doc_id)
    raise ValueError(f"unsupported file extension: {suffix!r}")
