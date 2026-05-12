#!/usr/bin/env bash
# CI lint: fail the build if any model family name leaks into user-facing source.
# Allowed exception: sidecar/dms/llm/runner.py (which lives behind compiled Python).
#
# Scope (intentional): scans only `ui/src`, `sidecar/dms`, `src-tauri/src`.
# Engine asset filenames (engine/*.dll, *.dylib, *.so, ai-engine-core[.exe]) and
# the build-time `engine-recipe.json` + `.github/workflows/*` are NOT scanned —
# those are build-time configuration / vendor binaries, not user-facing source,
# and the upstream llama.cpp DLL names are load-bearing (the engine binary's
# import table is hard-linked to `llama.dll`, `ggml-base.dll`, etc.).
# DO NOT widen this lint recursively across the repo or it will start matching
# the engine recipe and the bundled DLLs.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

BANNED='qwen|Qwen|llama|Llama|ollama|huggingface|HuggingFace'

violations=0

scan() {
  local dir="$1"
  local exclude="${2:-}"
  local hits
  if [ -n "$exclude" ]; then
    hits=$(grep -rEn --include='*.ts' --include='*.tsx' --include='*.py' --include='*.rs' --include='*.json' \
      "$BANNED" "$dir" 2>/dev/null | grep -v "$exclude" || true)
  else
    hits=$(grep -rEn --include='*.ts' --include='*.tsx' --include='*.py' --include='*.rs' --include='*.json' \
      "$BANNED" "$dir" 2>/dev/null || true)
  fi
  if [ -n "$hits" ]; then
    echo "Forbidden model-family strings in $dir:" >&2
    echo "$hits" >&2
    violations=$((violations + 1))
  fi
}

scan "$ROOT/ui/src"
scan "$ROOT/sidecar/dms" "sidecar/dms/llm/runner.py"
scan "$ROOT/src-tauri/src"

if [ $violations -gt 0 ]; then
  echo "source-hiding lint failed ($violations directories)" >&2
  exit 1
fi
echo "source-hiding lint passed"
