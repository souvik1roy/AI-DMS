"""Structured logging for the OrganiseAI sidecar.

Writes one JSON object per line to `<app_data>/logs/sidecar-YYYY-MM-DD.jsonl`,
rotated at midnight with 30-day retention. A `SensitiveFilter` scrubs known
secret fields (bearer tokens, API keys, OAuth redirect tokens) before the
record reaches disk.

Usage:
    from dms.logging_setup import configure
    configure(app_data, debug=bool(os.environ.get("DMS_DEBUG")))
"""
from __future__ import annotations

import json
import logging
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

LOG_FILENAME_PREFIX = "sidecar-"
LOG_FILENAME_SUFFIX = ".jsonl"

# Field names whose values should be redacted regardless of where they appear in
# the record's extras. Matched case-insensitively, substring match.
_SENSITIVE_KEY_PATTERNS = (
    "api_key",
    "apikey",
    "bearer",
    "authorization",
    "auth_token",
    "access_token",
    "refresh_token",
    "secret",
    "password",
)

# Substrings inside the formatted message that indicate likely secrets to mask.
_SENSITIVE_VALUE_PATTERN = re.compile(
    r"(?i)(bearer\s+[A-Za-z0-9._\-]+|ak_[A-Za-z0-9._\-]+|sk_[A-Za-z0-9._\-]+)"
)


def _is_sensitive_key(name: str) -> bool:
    lower = name.lower()
    return any(p in lower for p in _SENSITIVE_KEY_PATTERNS)


def _redact(value: Any) -> Any:
    """Walk dicts/lists, redacting values whose keys match the denylist."""
    if isinstance(value, dict):
        return {k: ("<redacted>" if _is_sensitive_key(k) else _redact(v)) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact(v) for v in value]
    return value


def _scrub_message(msg: str) -> str:
    return _SENSITIVE_VALUE_PATTERN.sub("<redacted>", msg)


# Standard LogRecord attributes we should NOT echo into the extras blob.
_STD_ATTRS = frozenset(
    {
        "name",
        "msg",
        "args",
        "levelname",
        "levelno",
        "pathname",
        "filename",
        "module",
        "exc_info",
        "exc_text",
        "stack_info",
        "lineno",
        "funcName",
        "created",
        "msecs",
        "relativeCreated",
        "thread",
        "threadName",
        "processName",
        "process",
        "asctime",
        "message",
        "taskName",
    }
)


class JsonFormatter(logging.Formatter):
    """Emit each record as one JSON line, with extras flattened in."""

    def format(self, record: logging.LogRecord) -> str:
        message = record.getMessage()
        payload: dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "msg": _scrub_message(message),
        }
        extras = {
            k: v for k, v in record.__dict__.items() if k not in _STD_ATTRS and not k.startswith("_")
        }
        if extras:
            payload["extra"] = _redact(extras)
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str, ensure_ascii=False)


RETENTION_DAYS = 30


def _today_path(logs_dir: Path) -> Path:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return logs_dir / f"{LOG_FILENAME_PREFIX}{today}{LOG_FILENAME_SUFFIX}"


def _sweep_old_logs(logs_dir: Path, retention_days: int) -> None:
    cutoff = time.time() - retention_days * 86400
    for f in logs_dir.glob(f"{LOG_FILENAME_PREFIX}*{LOG_FILENAME_SUFFIX}"):
        try:
            if f.stat().st_mtime < cutoff:
                f.unlink()
        except OSError:
            pass


def configure(app_data: Path, *, debug: bool = False) -> Path:
    """Wire up file + stderr logging. Returns the logs directory path."""
    logs_dir = app_data / "logs"
    (logs_dir / "jobs").mkdir(parents=True, exist_ok=True)
    _sweep_old_logs(logs_dir, RETENTION_DAYS)

    root = logging.getLogger("dms")
    root.setLevel(logging.DEBUG if debug else logging.INFO)
    # Wipe existing handlers (sidecar may be re-configured in tests).
    for h in list(root.handlers):
        root.removeHandler(h)
    root.propagate = False

    json_formatter = JsonFormatter()

    file_handler = logging.FileHandler(_today_path(logs_dir), encoding="utf-8")
    file_handler.setFormatter(json_formatter)
    file_handler.setLevel(logging.DEBUG if debug else logging.INFO)
    root.addHandler(file_handler)

    # Plain console handler — keeps `DMS_DEBUG=1` developer ergonomics.
    if debug:
        stream = logging.StreamHandler(stream=sys.stderr)
        stream.setFormatter(json_formatter)
        stream.setLevel(logging.DEBUG)
        root.addHandler(stream)

    root.info(
        "logging configured",
        extra={"logs_dir": str(logs_dir), "debug": debug, "file": file_handler.baseFilename},
    )
    return logs_dir
