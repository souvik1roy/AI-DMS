#!/usr/bin/env bash
# Browser-mode developer launcher: boots the sidecar + Vite dev server WITHOUT Tauri.
# Useful when Rust/tauri-cli isn't installed yet but you want to see the frontend.
#
# Writes the sidecar handshake to ui/public/_dms_dev_handshake.json so the React
# app can read it on first call.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HANDSHAKE_PATH="$ROOT/ui/public/_dms_dev_handshake.json"
SIDECAR_LOG="$ROOT/.smoke/sidecar.log"
mkdir -p "$ROOT/.smoke" "$ROOT/ui/public"

if [ ! -x "$ROOT/sidecar/.venv/bin/python" ]; then
  echo "Sidecar venv missing. Run: python3.11 -m venv sidecar/.venv && sidecar/.venv/bin/pip install -e ./sidecar"
  exit 1
fi

# Load Supabase / OpenAI / bearer-token env vars from the repo-root .env
# (gitignored). Falls back to sidecar/.env if a developer kept the old layout.
for env_file in "$ROOT/.env" "$ROOT/sidecar/.env"; do
  if [ -f "$env_file" ]; then
    set -a
    # shellcheck disable=SC1091
    . "$env_file"
    set +a
  fi
done

missing=()
[ -z "${DATABASE_URL:-}" ]              && missing+=("DATABASE_URL")
[ -z "${OPENAI_API_KEY:-}" ]            && missing+=("OPENAI_API_KEY")
[ -z "${SUPABASE_URL:-}" ]              && missing+=("SUPABASE_URL")
[ -z "${SUPABASE_SERVICE_ROLE_KEY:-}" ] && missing+=("SUPABASE_SERVICE_ROLE_KEY")
if [ ${#missing[@]} -gt 0 ]; then
  echo "Missing env vars in .env: ${missing[*]}" >&2
  echo "Open .env in this repo root and fill them in (see comments for where to find each value)." >&2
  exit 1
fi

# Pre-flight: multi-modal extractors need ffmpeg (audio/video) and soffice (Office).
bin_missing=()
command -v ffmpeg >/dev/null 2>&1 || bin_missing+=("ffmpeg")
if ! command -v soffice >/dev/null 2>&1 && ! command -v libreoffice >/dev/null 2>&1; then
  if [ ! -x "/Applications/LibreOffice.app/Contents/MacOS/soffice" ]; then
    bin_missing+=("libreoffice")
  fi
fi
if [ ${#bin_missing[@]} -gt 0 ]; then
  echo "Warning: multi-modal extractors need these system binaries: ${bin_missing[*]}" >&2
  echo "  macOS:  brew install ffmpeg && brew install --cask libreoffice" >&2
  echo "  Debian: apt-get install ffmpeg libreoffice" >&2
  echo "Continuing anyway — uploads that need them will fail with a clear error." >&2
fi

cleanup() {
  [ -n "${SIDECAR_PID:-}" ] && kill "$SIDECAR_PID" 2>/dev/null || true
  [ -n "${VITE_PID:-}" ] && kill "$VITE_PID" 2>/dev/null || true
  rm -f "$HANDSHAKE_PATH"
}
trap cleanup EXIT INT TERM

echo "==> Booting sidecar"
("$ROOT/sidecar/.venv/bin/python" -m dms 2>"$SIDECAR_LOG" | tee /tmp/dms-handshake.line) &
SIDECAR_PID=$!
sleep 1

# Pull the handshake JSON line.
HANDSHAKE=$(head -n 1 /tmp/dms-handshake.line || true)
if [ -z "$HANDSHAKE" ]; then
  # Wait a touch longer; uvicorn boot can take a second.
  sleep 2
  HANDSHAKE=$(head -n 1 /tmp/dms-handshake.line || true)
fi
if [ -z "$HANDSHAKE" ]; then
  echo "Sidecar produced no handshake. Log:"
  cat "$SIDECAR_LOG"
  exit 1
fi

echo "$HANDSHAKE" > "$HANDSHAKE_PATH"
echo "    handshake -> $HANDSHAKE_PATH"
echo "    sidecar log -> $SIDECAR_LOG"

echo "==> Starting Vite dev server"
cd "$ROOT/ui"
pnpm dev &
VITE_PID=$!

wait $SIDECAR_PID $VITE_PID
