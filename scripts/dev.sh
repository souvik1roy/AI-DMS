#!/usr/bin/env bash
# Run the app in dev mode. Assumes prerequisites are installed:
#   - Rust toolchain (cargo, tauri-cli installed via `cargo install tauri-cli --version '^2.0.0'`)
#   - Node 20+ and pnpm
#   - Python 3.11+ with a venv at sidecar/.venv (pip install -e ./sidecar)
#   - engine/ provisioned (run scripts/fetch-engine.sh first)

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

if [ ! -d "$ROOT/sidecar/.venv" ]; then
  echo "==> Creating sidecar venv"
  python3 -m venv "$ROOT/sidecar/.venv"
  "$ROOT/sidecar/.venv/bin/pip" install -e "$ROOT/sidecar"
fi

if [ ! -d "$ROOT/ui/node_modules" ]; then
  echo "==> Installing UI deps"
  (cd "$ROOT/ui" && pnpm install)
fi

if [ ! -x "$ROOT/engine/ai-engine-core" ]; then
  echo "==> WARNING: $ROOT/engine/ai-engine-core not found. The sidecar will fail to start engines."
  echo "    Run scripts/fetch-engine.sh and place the llama-server binary as ai-engine-core."
fi

cd "$ROOT/src-tauri"
exec cargo tauri dev
