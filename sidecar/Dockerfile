# Multi-stage build: one image hosts both the React UI and the FastAPI service.
# Build context must be the repo root (see render.yaml: dockerContext=.) so we
# can COPY both `ui/` and `sidecar/`.

# ---------- Stage 1: build the UI ----------
FROM node:20-slim AS ui-build
RUN corepack enable && corepack prepare pnpm@9.0.0 --activate
WORKDIR /ui
COPY ui/package.json ui/pnpm-lock.yaml /ui/
RUN pnpm install --frozen-lockfile
COPY ui/ /ui/
# The bearer token is injected into index.html at serve time by FastAPI, so
# the static build is token-free. VITE_DMS_BASE_URL stays empty -> same-origin.
RUN pnpm run build

# ---------- Stage 2: Python sidecar + UI dist ----------
FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DMS_WEB_MODE=1 \
    PORT=8080 \
    DMS_UI_DIST=/app/dist

# PyMuPDF ships manylinux wheels; ffmpeg + libreoffice are needed for
# audio/video transcoding and Office -> PDF rendering.
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        libreoffice-core \
        libreoffice-writer \
        libreoffice-calc \
        libreoffice-impress \
        fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first (layer cache survives source edits). The placeholder
# package lets `pip install -e .` succeed; the real `dms/` is copied next.
COPY sidecar/pyproject.toml /app/pyproject.toml
RUN mkdir -p /app/dms && touch /app/dms/__init__.py \
    && pip install --no-cache-dir -e .

COPY sidecar/dms /app/dms
COPY --from=ui-build /ui/dist /app/dist

# Drop root for runtime.
RUN useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8080

# Shell form expands $PORT (Render injects this at runtime).
CMD ["sh", "-c", "exec python -m dms --host 0.0.0.0 --port ${PORT:-8080} --no-handshake"]
