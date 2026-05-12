#!/usr/bin/env python3
"""Install the AI engine binary + model weights into ./engine/.

Reads `engine-recipe.json` at the repo root. For the host platform, downloads the
runtime tarball + per-engine model files, verifies sha256, and writes
`engine/engine.json` so the sidecar can resolve files by cover name.

Usage:
    python3 scripts/install_engine.py                # install / verify
    python3 scripts/install_engine.py --record-hashes # populate <populate...> sha256
                                                     # placeholders in the recipe
    python3 scripts/install_engine.py --force        # re-download even if files match
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
RECIPE_PATH = ROOT / "engine-recipe.json"
ENGINE_DIR = ROOT / "engine"
MANIFEST_PATH = ENGINE_DIR / "engine.json"

# Opaque filenames that the sidecar expects. These mirror the constants in
# `sidecar/dms/config.py` and are deliberately stable across releases.
VISION_MODEL = "v.bin"
VISION_MMPROJ = "vproj.bin"
REASONER_MODEL = "t.bin"
ENGINE_BINARY = "ai-engine-core.exe" if sys.platform == "win32" else "ai-engine-core"

HASH_PLACEHOLDER = "<populate-after-first-fetch>"


# ---------- helpers ----------

def host_target() -> str:
    s = platform.system().lower()
    m = platform.machine().lower()
    if s == "darwin" and m == "arm64":
        return "macos-arm64"
    if s == "darwin" and m in ("x86_64", "amd64"):
        return "macos-x64"
    if s == "linux" and m in ("x86_64", "amd64"):
        return "ubuntu-x64"
    sys.exit(f"Unsupported host: {platform.system()} {platform.machine()}")


def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            data = f.read(chunk)
            if not data:
                break
            h.update(data)
    return h.hexdigest()


def human_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{n} B"
        n = n / 1024
    return f"{n:.1f} GB"


def download(url: str, dest: Path) -> Path:
    """Download via curl (uses system trust store) with a progress bar."""
    partial = dest.with_suffix(dest.suffix + ".partial")
    partial.parent.mkdir(parents=True, exist_ok=True)
    print(f"    downloading {dest.name}")
    try:
        subprocess.run(  # noqa: S603, S607
            ["curl", "-L", "--fail", "--progress-bar", "-o", str(partial), url],
            check=True,
        )
    except subprocess.CalledProcessError as e:
        partial.unlink(missing_ok=True)
        sys.exit(f"download failed for {url}: curl exit {e.returncode}")
    return partial


def ensure_file(url: str, expected_sha: str | None, dest: Path, *, force: bool) -> str:
    """Make sure `dest` exists and matches sha256. Returns actual sha256."""
    if dest.exists() and not force:
        if expected_sha and expected_sha != HASH_PLACEHOLDER:
            actual = sha256_file(dest)
            if actual == expected_sha:
                print(f"    have {dest.name} ({human_size(dest.stat().st_size)})")
                return actual
            print(f"    sha256 mismatch on {dest.name}; refetching")
            dest.unlink()
        else:
            # No expected hash yet — keep existing file and just compute its hash.
            actual = sha256_file(dest)
            print(f"    have {dest.name} ({human_size(dest.stat().st_size)})")
            return actual

    partial = download(url, dest)
    actual = sha256_file(partial)
    if expected_sha and expected_sha != HASH_PLACEHOLDER and actual != expected_sha:
        partial.unlink(missing_ok=True)
        sys.exit(
            f"sha256 mismatch for {dest.name}:\n"
            f"  expected {expected_sha}\n"
            f"  actual   {actual}"
        )
    partial.rename(dest)
    return actual


# ---------- runtime tarball handling ----------

def install_runtime(url: str, expected_sha: str | None, *, force: bool) -> str:
    """Fetch engine tarball, extract binary + dylibs into ENGINE_DIR."""
    tgz = ENGINE_DIR / f".runtime-{host_target()}.tar.gz"
    binary_present = (ENGINE_DIR / ENGINE_BINARY).exists()

    # Fast path: binary already extracted AND we have a recorded sha for the
    # tarball. Skip the redundant fetch on every install.
    if binary_present and not force and expected_sha and expected_sha != HASH_PLACEHOLDER:
        print(f"    have {ENGINE_BINARY} (sha {expected_sha[:12]}…)")
        return expected_sha

    actual_sha = ensure_file(url, expected_sha, tgz, force=force)

    if binary_present and not force:
        tgz.unlink(missing_ok=True)
        return actual_sha

    with tempfile.TemporaryDirectory() as td:
        with tarfile.open(tgz, "r:gz") as tar:
            tar.extractall(td)  # noqa: S202 — release tarball, trusted
        # Locate the server binary (named `llama-server` in the upstream archive).
        # We rename it to ai-engine-core. Tolerate the rename if it ever happens upstream.
        bin_path: Path | None = None
        for cand in ("llama-server", "llama-server.exe", "ai-engine-core", "ai-engine-core.exe"):
            for p in Path(td).rglob(cand):
                bin_path = p
                break
            if bin_path:
                break
        if not bin_path:
            sys.exit("could not find engine binary inside runtime archive")

        target = ENGINE_DIR / ENGINE_BINARY
        shutil.copy2(bin_path, target)
        target.chmod(0o755)

        # Copy sibling shared libraries (dylib / so / dll) + metal files.
        for f in bin_path.parent.iterdir():
            if f.is_file() and f.suffix in {".dylib", ".so", ".dll", ".metal"}:
                shutil.copy2(f, ENGINE_DIR / f.name)
            elif f.is_file() and f.name.startswith("ggml-metal"):
                shutil.copy2(f, ENGINE_DIR / f.name)

    # Release tarballs use symlinks (libfoo.0.dylib → libfoo.0.X.Y.dylib) that
    # plain `copy2` flattened. Recreate the unversioned aliases.
    import re as _re
    for f in ENGINE_DIR.glob("lib*.0.*.dylib"):
        base = _re.sub(r"\.0\.[0-9.]+\.dylib$", ".0.dylib", f.name)
        alias = ENGINE_DIR / base
        if not alias.exists():
            alias.symlink_to(f.name)

    tgz.unlink(missing_ok=True)
    return actual_sha


# ---------- main flow ----------

def main() -> int:
    ap = argparse.ArgumentParser(prog="install_engine")
    ap.add_argument("--record-hashes", action="store_true",
                    help="Fetch everything, capture sha256s, and write them back into engine-recipe.json")
    ap.add_argument("--force", action="store_true",
                    help="Re-download every file even if it already exists with the right hash")
    args = ap.parse_args()

    if not RECIPE_PATH.exists():
        sys.exit(f"recipe not found: {RECIPE_PATH}")
    recipe: dict[str, Any] = json.loads(RECIPE_PATH.read_text(encoding="utf-8"))

    target = host_target()
    runtime_spec = recipe["runtime"]["targets"].get(target)
    if not runtime_spec:
        sys.exit(f"recipe has no runtime target for host: {target}")

    ENGINE_DIR.mkdir(parents=True, exist_ok=True)

    print(f"==> installing engine for {target} (runtime tag {recipe['runtime']['tag']})")
    runtime_sha = install_runtime(
        url=runtime_spec["url"], expected_sha=runtime_spec.get("sha256"), force=args.force,
    )

    print("==> vision engine")
    vision_spec = recipe["engines"]["vision"]
    vision_model_sha = ensure_file(
        vision_spec["model"]["url"], vision_spec["model"].get("sha256"),
        ENGINE_DIR / VISION_MODEL, force=args.force,
    )
    vision_mmproj_sha = ensure_file(
        vision_spec["mmproj"]["url"], vision_spec["mmproj"].get("sha256"),
        ENGINE_DIR / VISION_MMPROJ, force=args.force,
    )

    print("==> reasoning engine")
    reasoner_spec = recipe["engines"]["reasoner"]
    reasoner_model_sha = ensure_file(
        reasoner_spec["model"]["url"], reasoner_spec["model"].get("sha256"),
        ENGINE_DIR / REASONER_MODEL, force=args.force,
    )

    # Optionally record discovered hashes back into the recipe.
    if args.record_hashes:
        updated = False
        if recipe["runtime"]["targets"][target].get("sha256") in (None, "", HASH_PLACEHOLDER):
            recipe["runtime"]["targets"][target]["sha256"] = runtime_sha
            updated = True
        for kind, sha in (
            ("vision", "model", vision_model_sha),
            ("vision", "mmproj", vision_mmproj_sha),
            ("reasoner", "model", reasoner_model_sha),
        ) if False else (
            ("vision/model", vision_model_sha),
            ("vision/mmproj", vision_mmproj_sha),
            ("reasoner/model", reasoner_model_sha),
        ):
            engine, field = kind.split("/")
            slot = recipe["engines"][engine][field]
            if slot.get("sha256") in (None, "", HASH_PLACEHOLDER):
                slot["sha256"] = sha
                updated = True
        if updated:
            RECIPE_PATH.write_text(json.dumps(recipe, indent=2) + "\n", encoding="utf-8")
            print(f"==> recipe updated with recorded hashes: {RECIPE_PATH}")

    # Always write a fresh runtime manifest. The schema below is the only contract
    # between the installer and the sidecar — no upstream model identifiers appear.
    manifest = {
        "schema_version": 1,
        "runtime": {
            "name": ENGINE_BINARY,
            "version": recipe["runtime"]["tag"],
        },
        "engines": {
            "vision": {
                "display_name": vision_spec["display_name"],
                "version": vision_spec["version"],
                "model_file": VISION_MODEL,
                "model_sha256": vision_model_sha,
                "model_size": (ENGINE_DIR / VISION_MODEL).stat().st_size,
                "mmproj_file": VISION_MMPROJ,
                "mmproj_sha256": vision_mmproj_sha,
                "mmproj_size": (ENGINE_DIR / VISION_MMPROJ).stat().st_size,
            },
            "reasoner": {
                "display_name": reasoner_spec["display_name"],
                "version": reasoner_spec["version"],
                "model_file": REASONER_MODEL,
                "model_sha256": reasoner_model_sha,
                "model_size": (ENGINE_DIR / REASONER_MODEL).stat().st_size,
            },
        },
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"==> manifest written: {MANIFEST_PATH}")

    print()
    print("Engine ready:")
    for entry in sorted(ENGINE_DIR.iterdir()):
        try:
            size = human_size(entry.stat().st_size)
        except OSError:
            size = "?"
        kind = "→" if entry.is_symlink() else " "
        print(f"  {kind} {entry.name:40s} {size}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
