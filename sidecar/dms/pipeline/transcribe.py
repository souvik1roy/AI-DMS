"""Audio / video transcription helpers.

We trim audio (or extract the audio track from video) to the first
`AUDIO_TRIM_SECONDS` using ffmpeg, then send the trimmed mp3 to OpenAI's
speech-to-text API. The resulting transcript powers both classification and
the sidecar `.transcript.txt` saved next to the source file.
"""
from __future__ import annotations

import io
import logging
import shutil
import subprocess

from dms.config import AUDIO_TRIM_SECONDS, FFMPEG_BIN, OPENAI_STT_MODEL
from dms.llm.openai_client import get_client

log = logging.getLogger("dms.transcribe")


class TranscriptionError(RuntimeError):
    pass


def _ffmpeg() -> str:
    path = shutil.which(FFMPEG_BIN)
    if not path:
        raise TranscriptionError(
            f"ffmpeg not found on PATH ('{FFMPEG_BIN}'). "
            "Install via `brew install ffmpeg` (macOS) or "
            "`apt-get install ffmpeg` (Debian)."
        )
    return path


def trim_to_audio_mp3(body: bytes, seconds: int = AUDIO_TRIM_SECONDS) -> bytes:
    """Take audio or video bytes; emit a mono 16 kbps mp3 of the first `seconds`.

    Works for both audio-only inputs and videos (`-vn` discards any video
    stream). Pipes through stdin/stdout to avoid touching disk.
    """
    binary = _ffmpeg()
    cmd = [
        binary,
        "-loglevel", "error",
        "-y",
        "-i", "pipe:0",
        "-t", str(seconds),
        "-vn",
        "-ac", "1",
        "-ar", "16000",
        "-b:a", "16k",
        "-f", "mp3",
        "pipe:1",
    ]
    try:
        result = subprocess.run(  # noqa: S603 — args fully controlled.
            cmd,
            input=body,
            capture_output=True,
            timeout=120,
            check=False,
        )
    except subprocess.TimeoutExpired as e:
        raise TranscriptionError("ffmpeg timed out") from e

    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace")[:400]
        raise TranscriptionError(f"ffmpeg exited {result.returncode}: {stderr}")
    if not result.stdout:
        raise TranscriptionError(
            "ffmpeg produced no audio output (source may have no audio track)"
        )
    return result.stdout


def transcribe(audio_mp3: bytes, *, filename_hint: str = "clip.mp3") -> str:
    """Send the (already-trimmed) mp3 bytes to OpenAI STT. Returns the text."""
    client = get_client()
    buf = io.BytesIO(audio_mp3)
    buf.name = filename_hint
    resp = client.audio.transcriptions.create(
        model=OPENAI_STT_MODEL,
        file=buf,
        response_format="text",
    )
    if isinstance(resp, str):
        return resp.strip()
    # Some SDK versions return an object with `.text`.
    text = getattr(resp, "text", None) or ""
    return text.strip()
