#!/usr/bin/env python3
"""CI-only engine provisioner.

Like `install_engine.py`, but takes an explicit `--target` instead of detecting
the host. Designed to run on a CI runner of one platform while producing the
asset layout for any of the four supported targets:

    macos-arm64 | macos-x64 | ubuntu-x64 | windows-x64

For each invocation it:
  1. Reads `engine-recipe.json`.
  2. Downloads the per-target runtime archive (.tar.gz or .zip) via urllib so
     Windows runners without curl still work.
  3. Verifies sha256 (hard-fails in CI when the recipe still has the
     `<populate-after-first-fetch>` placeholder).
  4. Extracts `llama-server[.exe]` and copies it to `engine/ai-engine-core[.exe]`.
  5. Copies sibling shared libraries (`.dylib`, `.so`, `.dll`, `.metal`).
  6. On Windows, also stages the vendored VC++ runtime DLLs from
     `vendor/vcredist/win-x64/` so the engine runs without a system-wide
     redistributable install.
  7. Downloads the three GGUF model files, names them `v.bin`/`vproj.bin`/`t.bin`.
  8. Writes `engine/engine.json` (no model family names; opaque names only).

Usage:
    python scripts/ci_provision_engine.py --target macos-arm64
    python scripts/ci_provision_engine.py --target windows-x64 --force
    python scripts/ci_provision_engine.py --target ubuntu-x64 --record-hashes
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import tarfile
import tempfile
import urllib.request
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
RECIPE_PATH = ROOT / "engine-recipe.json"
ENGINE_DIR = ROOT / "engine"
MANIFEST_PATH = ENGINE_DIR / "engine.json"
VCREDIST_DIR = ROOT / "vendor" / "vcredist" / "win-x64"

VISION_MODEL = "v.bin"
VISION_MMPROJ = "vproj.bin"
REASONER_MODEL = "t.bin"

HASH_PLACEHOLDER = "<populate-after-first-fetch>"

VALID_TARGETS = ("macos-arm64", "macos-x64", "ubuntu-x64", "windows-x64")

VCREDIST_DLLS = ("vcruntime140.dll", "vcruntime140_1.dll", "msvcp140.dll")


# ---------- helpers ----------

def is_windows_target(target: str) -> bool:
    return target == "windows-x64"


def engine_binary_name(target: str) -> str:
    return "ai-engine-core.exe" if is_windows_target(target) else "ai-engine-core"


def lib_suffixes_for(target: str) -> set[str]:
    if target == "windows-x64":
        return {".dll"}
    if target == "ubuntu-x64":
        return {".so"}
    return {".dylib", ".metal"}


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
    f = float(n)
    for unit in ("B", "KB", "MB", "GB"):
        if f < 1024 or unit == "GB":
            return f"{f:.1f} {unit}" if unit != "B" else f"{int(f)} B"
        f = f / 1024
    return f"{f:.1f} GB"


def download(url: str, dest: Path) -> Path:
    partial = dest.with_suffix(dest.suffix + ".partial")
    partial.parent.mkdir(parents=True, exist_ok=True)
    print(f"    downloading {dest.name}  <- {url}")
    try:
        with urllib.request.urlopen(url) as r, partial.open("wb") as out:  # noqa: S310
            shutil.copyfileobj(r, out, length=1 << 20)
    except Exception as e:  # noqa: BLE001
        partial.unlink(missing_ok=True)
        sys.exit(f"download failed for {url}: {e}")
    return partial


def ensure_file(url: str, expected_sha: str | None, dest: Path, *, force: bool) -> str:
    in_ci = os.environ.get("CI", "").lower() == "true"
    if expected_sha == HASH_PLACEHOLDER and in_ci:
        sys.exit(
            f"refusing to publish unverified binary: {dest.name} has sha256 "
            f"{HASH_PLACEHOLDER!r} in engine-recipe.json. Run "
            "`python scripts/ci_provision_engine.py --target X --record-hashes` "
            "on a developer machine and commit the resulting recipe."
        )

    if dest.exists() and not force:
        if expected_sha and expected_sha != HASH_PLACEHOLDER:
            actual = sha256_file(dest)
            if actual == expected_sha:
                print(f"    have {dest.name} ({human_size(dest.stat().st_size)})")
                return actual
            print(f"    sha256 mismatch on {dest.name}; refetching")
            dest.unlink()
        else:
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


def extract_archive(archive: Path, into: Path) -> None:
    name = archive.name.lower()
    if name.endswith(".zip"):
        with zipfile.ZipFile(archive, "r") as zf:
            zf.extractall(into)
    elif name.endswith((".tar.gz", ".tgz")):
        with tarfile.open(archive, "r:gz") as tar:
            tar.extractall(into)  # noqa: S202 — release archive, trusted
    else:
        sys.exit(f"unknown archive format: {archive}")


def archive_filename_for(target: str, url: str) -> str:
    # Use the URL's basename so we preserve the right extension (.zip vs .tar.gz).
    return f".runtime-{target}-{url.rsplit('/', 1)[-1]}"


def find_server_binary(root: Path) -> Path | None:
    candidates = ("llama-server", "llama-server.exe", "ai-engine-core", "ai-engine-core.exe")
    for cand in candidates:
        for p in root.rglob(cand):
            return p
    return None


def stage_vcredist(target_engine_dir: Path) -> None:
    if not VCREDIST_DIR.exists():
        sys.exit(
            f"FATAL: Windows build requires VC++ DLLs at {VCREDIST_DIR}. "
            f"See vendor/vcredist/README.md for one-time setup instructions."
        )
    missing = [name for name in VCREDIST_DLLS if not (VCREDIST_DIR / name).exists()]
    if missing:
        sys.exit(
            f"FATAL: missing VC++ DLLs in {VCREDIST_DIR}: {missing}. "
            f"See vendor/vcredist/README.md."
        )
    for name in VCREDIST_DLLS:
        shutil.copy2(VCREDIST_DIR / name, target_engine_dir / name)
    print(f"    staged VC++ runtime DLLs: {', '.join(VCREDIST_DLLS)}")


def install_runtime(target: str, url: str, expected_sha: str | None, *, force: bool) -> str:
    archive = ENGINE_DIR / archive_filename_for(target, url)
    binary_name = engine_binary_name(target)
    binary_present = (ENGINE_DIR / binary_name).exists()

    if binary_present and not force and expected_sha and expected_sha != HASH_PLACEHOLDER:
        print(f"    have {binary_name} (sha {expected_sha[:12]}…)")
        return expected_sha

    actual_sha = ensure_file(url, expected_sha, archive, force=force)

    if binary_present and not force:
        archive.unlink(missing_ok=True)
        return actual_sha

    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        extract_archive(archive, td_path)
        bin_path = find_server_binary(td_path)
        if not bin_path:
            sys.exit("could not find engine binary inside runtime archive")

        target_bin = ENGINE_DIR / binary_name
        shutil.copy2(bin_path, target_bin)
        if not is_windows_target(target):
            target_bin.chmod(0o755)

        # Copy sibling shared libraries.
        wanted = lib_suffixes_for(target)
        for f in bin_path.parent.iterdir():
            if not f.is_file():
                continue
            if f.suffix.lower() in wanted or f.name.startswith("ggml-metal"):
                shutil.copy2(f, ENGINE_DIR / f.name)

    # On macOS, recreate the unversioned dylib aliases that release archives
    # use (libfoo.0.dylib → libfoo.0.X.Y.dylib).
    if target.startswith("macos-"):
        for f in ENGINE_DIR.glob("lib*.0.*.dylib"):
            base = re.sub(r"\.0\.[0-9.]+\.dylib$", ".0.dylib", f.name)
            alias = ENGINE_DIR / base
            if not alias.exists():
                alias.symlink_to(f.name)

    if is_windows_target(target):
        stage_vcredist(ENGINE_DIR)

    archive.unlink(missing_ok=True)
    return actual_sha


# ---------- main ----------

def main() -> int:
    ap = argparse.ArgumentParser(prog="ci_provision_engine")
    ap.add_argument("--target", required=True, choices=VALID_TARGETS)
    ap.add_argument("--force", action="store_true")
    ap.add_argument(
        "--record-hashes",
        action="store_true",
        help="Capture observed sha256s back into engine-recipe.json",
    )
    args = ap.parse_args()

    if not RECIPE_PATH.exists():
        sys.exit(f"recipe not found: {RECIPE_PATH}")
    recipe: dict[str, Any] = json.loads(RECIPE_PATH.read_text(encoding="utf-8"))

    runtime_spec = recipe["runtime"]["targets"].get(args.target)
    if not runtime_spec:
        sys.exit(f"recipe has no runtime target: {args.target}")

    ENGINE_DIR.mkdir(parents=True, exist_ok=True)

    print(f"==> provisioning engine for {args.target} (runtime tag {recipe['runtime']['tag']})")
    runtime_sha = install_runtime(
        args.target, runtime_spec["url"], runtime_spec.get("sha256"), force=args.force,
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

    if args.record_hashes:
        updated = False
        slot = recipe["runtime"]["targets"][args.target]
        if slot.get("sha256") in (None, "", HASH_PLACEHOLDER):
            slot["sha256"] = runtime_sha
            updated = True
        for path, sha in (
            (("engines", "vision", "model"), vision_model_sha),
            (("engines", "vision", "mmproj"), vision_mmproj_sha),
            (("engines", "reasoner", "model"), reasoner_model_sha),
        ):
            ref: Any = recipe
            for k in path:
                ref = ref[k]
            if ref.get("sha256") in (None, "", HASH_PLACEHOLDER):
                ref["sha256"] = sha
                updated = True
        if updated:
            RECIPE_PATH.write_text(json.dumps(recipe, indent=2) + "\n", encoding="utf-8")
            print(f"==> recipe updated with recorded hashes: {RECIPE_PATH}")

    manifest = {
        "schema_version": 1,
        "target": args.target,
        "runtime": {
            "name": engine_binary_name(args.target),
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
    print(f"Engine ready ({args.target}):")
    for entry in sorted(ENGINE_DIR.iterdir()):
        try:
            size = human_size(entry.stat().st_size)
        except OSError:
            size = "?"
        kind = "->" if entry.is_symlink() else "  "
        print(f"  {kind} {entry.name:40s} {size}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
