#!/usr/bin/env bash
# Thin shell wrapper around scripts/install_engine.py. JSON parsing + sha256
# verification lives in Python for portability and clarity.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$SCRIPT_DIR/install_engine.py" "$@"
