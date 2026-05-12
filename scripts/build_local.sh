#!/usr/bin/env bash
# Build the host-platform installer end-to-end and drop it into software/<triple>/.
#
# Order of operations:
#   1. Provision engine assets for the host target (idempotent — re-uses cached
#      tarballs and GGUFs in engine/).
#   2. Build the UI (pnpm).
#   3. Build the Nuitka sidecar.
#   4. Run cargo tauri build, which uses `externalBin` to pull the sidecar in
#      and `resources` to pull engine/ in.
#   5. Copy the resulting installer into software/<triple>/.
#
# Prerequisites:
#   - Rust toolchain (`cargo tauri build`)
#   - Node + pnpm
#   - Python 3.11+ with sidecar/.venv set up (see sidecar/README)
#   - Internet, the first time, to download the engine assets (cached afterward)
#   - On Windows: vendor/vcredist/win-x64/{vcruntime140,vcruntime140_1,msvcp140}.dll
#                 must exist (see vendor/vcredist/README.md).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT"

OS="$(uname -s)"
ARCH="$(uname -m)"
case "$OS-$ARCH" in
  Darwin-arm64)
    TARGET="aarch64-apple-darwin"
    ENGINE_TARGET="macos-arm64"
    ;;
  Darwin-x86_64)
    TARGET="x86_64-apple-darwin"
    ENGINE_TARGET="macos-x64"
    ;;
  Linux-x86_64)
    TARGET="x86_64-unknown-linux-gnu"
    ENGINE_TARGET="ubuntu-x64"
    ;;
  MINGW*|MSYS*|CYGWIN*|Windows_NT*)
    TARGET="x86_64-pc-windows-msvc"
    ENGINE_TARGET="windows-x64"
    ;;
  *) echo "Unsupported build host: $OS $ARCH" >&2; exit 1 ;;
esac

echo "=== Host: $OS $ARCH"
echo "=== Tauri target: $TARGET"
echo "=== Engine target: $ENGINE_TARGET"

# 1. Engine assets
PYTHON="${PYTHON:-sidecar/.venv/bin/python}"
if [ ! -x "$PYTHON" ] && [ -x "sidecar/.venv/Scripts/python.exe" ]; then
  PYTHON="sidecar/.venv/Scripts/python.exe"
fi
if [ ! -x "$PYTHON" ]; then
  echo "FATAL: $PYTHON not found. Create the sidecar venv first." >&2
  exit 1
fi

echo "=== Provisioning engine assets ($ENGINE_TARGET)"
"$PYTHON" scripts/ci_provision_engine.py --target "$ENGINE_TARGET"

# 2. UI
echo "=== Building UI"
pnpm -C ui install --frozen-lockfile
pnpm -C ui build

# 3. Sidecar
echo "=== Building sidecar (Nuitka)"
bash sidecar/build_nuitka.sh

# 4. Tauri
echo "=== Building Tauri bundle"
if ! command -v cargo-tauri >/dev/null 2>&1; then
  cargo install tauri-cli --version "^2.0.0" --locked
fi
(cd src-tauri && cargo tauri build --target "$TARGET")

# 5. Collect into software/
echo "=== Collecting installers into software/$TARGET/"
mkdir -p "software/$TARGET"
bundle_dir="src-tauri/target/$TARGET/release/bundle"
find "$bundle_dir" -type f \( \
  -name "*.dmg" -o \
  -name "*.msi" -o \
  -name "*-setup.exe" -o \
  -name "*.AppImage" \
\) -exec cp -v {} "software/$TARGET/" \;

ls -la "software/$TARGET/"
echo "=== Done. Installers in software/$TARGET/"
