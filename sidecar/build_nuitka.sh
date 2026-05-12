#!/usr/bin/env bash
# Compile the Python sidecar into a native binary using Nuitka.
#
# Output layout:
#   macOS / Linux: ../src-tauri/binaries/dms-sidecar-<triple>          (--onefile)
#   Windows:       ../src-tauri/binaries/dms-sidecar-<triple>.dist/    (--standalone)
#                  with the launcher exe at .../dms-sidecar.exe
#
# Why Windows is --standalone: Nuitka --onefile self-extracts to %TEMP%
# on each launch, which triggers Defender/SmartScreen scans and can stall
# past Tauri's handshake-wait window. Shipping a directory avoids that.
#
# Pre-reqs (one-time):
#   cd sidecar
#   python -m venv .venv && source .venv/bin/activate   (or .venv/Scripts/activate on Windows)
#   pip install -e .[build]
#
# Then:
#   ./build_nuitka.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

OS="$(uname -s)"
ARCH="$(uname -m)"
EXT=""
MODE="--onefile"
case "$OS-$ARCH" in
  Darwin-arm64)  TARGET="aarch64-apple-darwin" ;;
  Darwin-x86_64) TARGET="x86_64-apple-darwin" ;;
  Linux-x86_64)  TARGET="x86_64-unknown-linux-gnu" ;;
  MINGW*|MSYS*|CYGWIN*|Windows_NT*)
    TARGET="x86_64-pc-windows-msvc"
    EXT=".exe"
    # See header comment for why we use --standalone on Windows.
    MODE="--standalone"
    ;;
  *) echo "Unsupported build host: $OS $ARCH" >&2; exit 1 ;;
esac

OUT_DIR="../src-tauri/binaries"
mkdir -p "$OUT_DIR"
OUT_NAME="dms-sidecar-${TARGET}${EXT}"

echo "Building $OUT_NAME via Nuitka ($MODE)…"

# Explicit --include-package list. After the Composio removal Nuitka's static
# import graph misses some transitively-imported packages, so we name each one
# the sidecar actually loads at runtime.
INCLUDES=(
  --include-package=dms
  --include-package=uvicorn
  --include-package=fastapi
  --include-package=pydantic
  --include-package=httpx
  --include-package=pymupdf
  --include-package=PIL
  --include-package=docx
  --include-package=openpyxl
  --include-package=ulid
)

# --lto=no: LTO link of a project this size uses ~10+ GB RAM and is the
# bottleneck on 16 GB hosts. The non-LTO binary is 5–10 % larger but links in
# seconds instead of an hour with disk swap.
python -m nuitka \
  $MODE \
  --lto=no \
  --jobs=4 \
  --remove-output \
  --assume-yes-for-downloads \
  --output-filename="$OUT_NAME" \
  --output-dir="$OUT_DIR" \
  "${INCLUDES[@]}" \
  --include-package-data=dms \
  --noinclude-default-mode=nofollow \
  --plugin-enable=anti-bloat \
  --product-name="AI DMS Engine" \
  --file-description="AI DMS background service" \
  --copyright="Allys AI" \
  dms/__main__.py

if [ "$MODE" = "--onefile" ]; then
  chmod +x "$OUT_DIR/$OUT_NAME"
  echo "Done: $OUT_DIR/$OUT_NAME"
else
  # Standalone produces a .dist/ directory next to the launcher exe.
  STANDALONE_DIR="$OUT_DIR/dms-sidecar-${TARGET}.dist"
  echo "Done: $STANDALONE_DIR (launcher: $STANDALONE_DIR/$OUT_NAME)"
fi
