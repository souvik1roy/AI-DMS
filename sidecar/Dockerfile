FROM python:3.11-slim AS base

# PyMuPDF (used for PDF page rendering) ships manylinux wheels for x86_64 and
# arm64; no system libs needed.
# Multi-modal ingestion adds two system deps:
#   - ffmpeg for audio/video trim + format conversion
#   - libreoffice (core + writer + calc + impress) for Office → PDF rendering
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DMS_WEB_MODE=1 \
    PORT=8080

RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        libreoffice-core \
        libreoffice-writer \
        libreoffice-calc \
        libreoffice-impress \
        fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install dependencies first (cached across code changes).
COPY pyproject.toml /app/pyproject.toml
RUN mkdir -p /app/dms && touch /app/dms/__init__.py \
    && pip install --no-cache-dir -e .

# Copy the actual package contents.
COPY dms /app/dms

EXPOSE 8080

# `--host 0.0.0.0` for Render; `--no-handshake` skips the stdout handshake JSON.
# The bearer token is read from $DMS_BEARER_TOKEN (must be set in the environment).
CMD ["python", "-m", "dms", "--host", "0.0.0.0", "--port", "8080", "--no-handshake"]
