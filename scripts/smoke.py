#!/usr/bin/env python3
"""End-to-end sidecar smoke test.

Boots the sidecar as a subprocess (no Tauri shell), reads the handshake JSON
from stdout, then exercises every public endpoint with the bearer token from
the handshake. Prints a green/red summary per check.

Run from repo root:
    sidecar/.venv/bin/python scripts/smoke.py

Exit code is non-zero if any required check fails.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
SIDECAR_DIR = ROOT / "sidecar"
PYTHON = SIDECAR_DIR / ".venv" / "bin" / "python"


def call(
    base: str, token: str, path: str, *, method: str = "GET", body: dict[str, Any] | None = None
) -> tuple[int, dict[str, Any] | str]:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        f"{base}{path}",
        data=data,
        method=method,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:  # noqa: S310
            text = r.read().decode("utf-8")
            try:
                return r.status, json.loads(text)
            except json.JSONDecodeError:
                return r.status, text
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode("utf-8"))
        except Exception:  # noqa: BLE001
            return e.code, str(e)


GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
DIM = "\033[2m"
RESET = "\033[0m"

failures: list[str] = []
warnings: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    mark = f"{GREEN}✓{RESET}" if ok else f"{RED}✗{RESET}"
    print(f"  {mark} {name}{f'  {DIM}{detail}{RESET}' if detail else ''}")
    if not ok:
        failures.append(name)


def warn(name: str, detail: str = "") -> None:
    print(f"  {YELLOW}!{RESET} {name}{f'  {DIM}{detail}{RESET}' if detail else ''}")
    warnings.append(name)


def run_engine_smoke(base: str, token: str) -> None:
    """Real end-to-end: stage two synthetic PDFs, parse-and-file them through
    the bundled local engine, assert at least one file ends up in the
    destination. Boots the engine cold, so allow up to 5 minutes.
    """
    sys.path.insert(0, str(ROOT))
    from scripts.smoke_fixtures import write_fixtures  # type: ignore

    inbox = ROOT / ".smoke" / "inbox"
    organized = ROOT / ".smoke" / "organized"
    inbox.mkdir(parents=True, exist_ok=True)
    organized.mkdir(parents=True, exist_ok=True)
    fixtures = write_fixtures(inbox)
    check(f"wrote {len(fixtures)} synthetic PDF(s) to .smoke/inbox", bool(fixtures))

    s, body = call(
        base,
        token,
        "/runs/local_folder",
        method="POST",
        body={"folder_path": str(inbox), "destination_folder": str(organized)},
    )
    check(
        "/runs/local_folder accepted engine job",
        s == 200 and isinstance(body, dict) and "job_id" in body,
        str(body),
    )
    if not (isinstance(body, dict) and "job_id" in body):
        return
    jid = body["job_id"]

    deadline = time.monotonic() + 300
    final_status = "?"
    final_stats: dict[str, Any] = {}
    while time.monotonic() < deadline:
        s, jb = call(base, token, f"/jobs/{jid}")
        if s == 200 and isinstance(jb, dict):
            final_status = jb.get("status", "?")
            final_stats = jb.get("stats") or {}
            if final_status in ("done", "partial", "failed", "cancelled"):
                break
        time.sleep(2)
    check(
        "engine job reached done state",
        final_status == "done",
        f"status={final_status} stats={final_stats}",
    )
    check("engine parsed >= 1 doc", int(final_stats.get("parsed", 0)) >= 1, str(final_stats))
    check("engine filed >= 1 doc", int(final_stats.get("filed", 0)) >= 1, str(final_stats))
    filed = [p for p in organized.rglob("*") if p.is_file()]
    check("at least one file landed in .smoke/organized", bool(filed), f"{len(filed)} files")


def main() -> int:
    if not PYTHON.exists():
        print(f"{RED}sidecar venv not found at {PYTHON}{RESET}")
        print("Run: python3.12 -m venv sidecar/.venv && sidecar/.venv/bin/pip install -e ./sidecar")
        return 2

    env = dict(os.environ)
    env["DMS_APP_DATA"] = str(ROOT / ".smoke" / "app_data")
    env["DMS_LOCAL_DATA"] = str(ROOT / ".smoke" / "local_data")
    env["DMS_ORGANIZED_ROOT"] = str(ROOT / ".smoke" / "organized")
    env["DMS_DEBUG"] = "1"

    print(f"{DIM}Booting sidecar from {SIDECAR_DIR}…{RESET}")
    proc = subprocess.Popen(  # noqa: S603
        [str(PYTHON), "-m", "dms"],
        cwd=SIDECAR_DIR,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    try:
        # First stdout line is the handshake.
        handshake_line = proc.stdout.readline() if proc.stdout else ""
        if not handshake_line:
            err = proc.stderr.read() if proc.stderr else ""
            print(f"{RED}sidecar produced no handshake. stderr:{RESET}\n{err}")
            return 2
        try:
            hs = json.loads(handshake_line)
        except json.JSONDecodeError:
            print(f"{RED}invalid handshake line: {handshake_line!r}{RESET}")
            return 2

        port = hs["port"]
        token = hs["token"]
        base = f"http://127.0.0.1:{port}"
        print(f"{DIM}Sidecar listening on {base}{RESET}\n")

        # ---------- public health ----------
        # Poll until uvicorn finishes binding the port.
        s, body = 0, ""
        for _ in range(40):
            try:
                s, body = call(base, "", "/health")
                if s == 200:
                    break
            except urllib.error.URLError:
                pass
            time.sleep(0.25)
        check("/health responds without auth", s == 200 and isinstance(body, dict) and body.get("ok") is True, str(body))

        # ---------- bearer-token enforcement ----------
        s, _ = call(base, "wrong-token", "/jobs")
        check("Wrong token → 401", s == 401)
        s, _ = call(base, "", "/jobs")  # missing header
        check("No bearer header → 401", s == 401)

        # ---------- /paths ----------
        s, body = call(base, token, "/paths")
        check(
            "/paths returns OS-appropriate dirs",
            s == 200 and isinstance(body, dict) and "organized_root" in body,
            str(body),
        )

        # ---------- taxonomy bootstrap ----------
        s, body = call(base, token, "/taxonomy")
        check(
            "/taxonomy returns empty initial snapshot",
            s == 200 and isinstance(body, dict) and body.get("entities") == [],
            str(body),
        )

        # ---------- jobs initially empty ----------
        s, body = call(base, token, "/jobs")
        check("/jobs returns empty list", s == 200 and body == [], str(body))

        # ---------- cloud surface fully removed ----------
        s, _ = call(base, token, "/connections")
        check("/connections returns 404 (offline build)", s == 404)
        s, _ = call(base, token, "/schedules")
        check("/schedules returns 404 (offline build)", s == 404)

        # ---------- /runs/local_folder rejects missing folder cleanly ----------
        bogus = str(ROOT / ".smoke" / "definitely-does-not-exist")
        s, body = call(base, token, "/runs/local_folder", method="POST", body={"folder_path": bogus})
        check(
            "/runs/local_folder accepts request",
            s == 200 and isinstance(body, dict) and "job_id" in body,
            str(body),
        )
        # Wait briefly for the worker to mark it failed.
        if isinstance(body, dict) and "job_id" in body:
            jid = body["job_id"]
            for _ in range(20):
                s, jb = call(base, token, f"/jobs/{jid}")
                if (
                    s == 200
                    and isinstance(jb, dict)
                    and jb.get("status") in ("failed", "done", "partial")
                ):
                    break
                time.sleep(0.25)
            check(
                "missing folder produces failed job with error",
                isinstance(jb, dict)
                and jb.get("status") == "failed"
                and "not found" in (jb.get("error_message") or "").lower(),
                str(jb),
            )

        # ---------- end-to-end engine smoke (gated behind SMOKE_WITH_ENGINE=1) ----------
        if os.environ.get("SMOKE_WITH_ENGINE") == "1":
            run_engine_smoke(base, token)

        print()
        if failures:
            print(f"{RED}{len(failures)} failed:{RESET} {', '.join(failures)}")
            return 1
        if warnings:
            print(f"{YELLOW}{len(warnings)} warning(s); all required checks passed.{RESET}")
        else:
            print(f"{GREEN}All smoke checks passed.{RESET}")
        return 0
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    sys.exit(main())
