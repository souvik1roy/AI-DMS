"""Convert Microsoft / OpenDocument office files to PDF using headless
LibreOffice. The PDF bytes then flow into `pdf_pages.render_first_and_last`
so the rest of the pipeline behaves identically to a native PDF upload.
"""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from dms.config import LIBREOFFICE_BIN, LIBREOFFICE_TIMEOUT_SECONDS

log = logging.getLogger("dms.office")

_RESOLVED_BIN: str | None = None


class OfficeConversionError(RuntimeError):
    pass


def _find_libreoffice() -> str:
    """Locate the LibreOffice CLI. macOS ships it as `soffice`; Debian /
    Ubuntu as `libreoffice`. Honour `LIBREOFFICE_BIN` env override.
    """
    global _RESOLVED_BIN
    if _RESOLVED_BIN:
        return _RESOLVED_BIN
    if LIBREOFFICE_BIN and shutil.which(LIBREOFFICE_BIN):
        _RESOLVED_BIN = LIBREOFFICE_BIN
        return _RESOLVED_BIN
    for candidate in ("soffice", "libreoffice"):
        path = shutil.which(candidate)
        if path:
            _RESOLVED_BIN = path
            return path
    # macOS app bundle fallback
    mac_path = "/Applications/LibreOffice.app/Contents/MacOS/soffice"
    if os.path.exists(mac_path):
        _RESOLVED_BIN = mac_path
        return mac_path
    raise OfficeConversionError(
        "LibreOffice not found on PATH. Install via `brew install --cask libreoffice` "
        "(macOS) or `apt-get install libreoffice-core libreoffice-writer "
        "libreoffice-calc libreoffice-impress` (Debian)."
    )


def office_to_pdf(body: bytes, suffix: str) -> bytes:
    """Convert `body` (Office document of the given extension) into PDF bytes."""
    binary = _find_libreoffice()
    with tempfile.TemporaryDirectory(prefix="dms-office-") as tmp:
        src = Path(tmp) / f"input{suffix.lower()}"
        src.write_bytes(body)

        # `--user-profile` keeps each invocation isolated so concurrent jobs
        # don't lock the same LibreOffice profile dir.
        profile = Path(tmp) / "profile"
        profile.mkdir()
        try:
            result = subprocess.run(  # noqa: S603 — args fully controlled.
                [
                    binary,
                    "--headless",
                    "--norestore",
                    "--nolockcheck",
                    "--convert-to",
                    "pdf",
                    "--outdir",
                    tmp,
                    f"-env:UserInstallation=file://{profile}",
                    str(src),
                ],
                capture_output=True,
                timeout=LIBREOFFICE_TIMEOUT_SECONDS,
                check=False,
            )
        except subprocess.TimeoutExpired as e:
            raise OfficeConversionError(
                f"LibreOffice conversion timed out after {LIBREOFFICE_TIMEOUT_SECONDS}s "
                f"for {suffix}"
            ) from e

        if result.returncode != 0:
            stderr = result.stderr.decode("utf-8", errors="replace")[:400]
            raise OfficeConversionError(
                f"LibreOffice exited {result.returncode}: {stderr}"
            )

        pdf_path = Path(tmp) / f"{src.stem}.pdf"
        if not pdf_path.exists():
            # Some versions write a slightly different name; pick any *.pdf
            # produced in the output dir.
            pdfs = list(Path(tmp).glob("*.pdf"))
            if not pdfs:
                raise OfficeConversionError(
                    "LibreOffice produced no PDF output"
                )
            pdf_path = pdfs[0]
        return pdf_path.read_bytes()
