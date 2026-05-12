#!/usr/bin/env bash
# DEPRECATED — kept as a back-compat shim. Use scripts/install-engine.sh instead.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "fetch-engine.sh is deprecated; delegating to install-engine.sh" >&2
exec "$SCRIPT_DIR/install-engine.sh" "$@"
