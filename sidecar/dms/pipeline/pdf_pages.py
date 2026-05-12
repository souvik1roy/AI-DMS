"""Render the first and last page of a PDF to PNG bytes.

For non-PDF image inputs we don't render; both pages just reuse the input bytes.
"""
from __future__ import annotations

import io
from dataclasses import dataclass

from dms.config import PAGE_RENDER_DPI


@dataclass(frozen=True)
class RenderedPages:
    """Returned by `render_first_and_last`.

    `first_bytes` / `last_bytes` are PNG-encoded; `last_bytes` is None when the
    document is a single page. `image_content_type` describes what `first_bytes`
    holds when it's a passthrough image (not a render).
    """

    first_bytes: bytes
    last_bytes: bytes | None
    image_content_type: str


_IMAGE_MIMES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".heic": "image/heic",
    ".tiff": "image/tiff",
    ".tif": "image/tiff",
}


def render_first_and_last(data: bytes, suffix: str) -> RenderedPages:
    """Return PNG bytes for page 0 and page N-1 of a PDF, or pass an image through."""
    suffix = suffix.lower()
    if suffix in _IMAGE_MIMES:
        return RenderedPages(
            first_bytes=data,
            last_bytes=None,
            image_content_type=_IMAGE_MIMES[suffix],
        )

    # PDF path — render via PyMuPDF.
    import fitz  # type: ignore[import-not-found]

    doc = fitz.open(stream=data, filetype="pdf")
    try:
        page_count = doc.page_count
        if page_count == 0:
            raise ValueError("PDF has zero pages")
        zoom = PAGE_RENDER_DPI / 72.0
        matrix = fitz.Matrix(zoom, zoom)

        first_pix = doc.load_page(0).get_pixmap(matrix=matrix, alpha=False)
        first_buf = io.BytesIO()
        first_buf.write(first_pix.tobytes("png"))
        first_bytes = first_buf.getvalue()

        if page_count == 1:
            return RenderedPages(
                first_bytes=first_bytes,
                last_bytes=None,
                image_content_type="image/png",
            )

        last_pix = doc.load_page(page_count - 1).get_pixmap(matrix=matrix, alpha=False)
        last_bytes = last_pix.tobytes("png")
        return RenderedPages(
            first_bytes=first_bytes,
            last_bytes=last_bytes,
            image_content_type="image/png",
        )
    finally:
        doc.close()
