from __future__ import annotations

import logging
import os
import socket
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path

import httpx

from dms.config import (
    ENGINE_BINARY,
    REASONER_PORT,
    VISION_PORT,
    Paths,
)
from dms.llm.manifest import EngineManifest, EngineSpec

log = logging.getLogger("dms.llm")


# The user-facing name for either subprocess is intentionally generic; no model family is exposed.
class EngineKind:
    VISION = "vision"
    REASONER = "reasoner"


@dataclass
class EngineHandle:
    kind: str
    port: int
    base_url: str
    proc: subprocess.Popen[bytes]

    def stop(self) -> None:
        if self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.proc.kill()


class EngineRunner:
    """Owns the lifecycle of the two `ai-engine-core` subprocesses.

    The binary path and model filenames are resolved through the engine manifest
    (engine/engine.json), which carries the public cover names ("OpenGraph Vision",
    "OpenGraph Text") plus opaque local filenames. The runner starts each engine
    subprocess, waits for /health, and exposes a base_url callers can hit.
    """

    def __init__(self, paths: Paths) -> None:
        self.paths = paths
        self.manifest = EngineManifest.load(paths.engine_dir)
        self._handles: dict[str, EngineHandle] = {}
        self._lock = threading.Lock()

    # ---- public API ----

    def engine_info(self) -> list[EngineSpec]:
        return [self.manifest.vision(), self.manifest.reasoner()]

    def vision(self) -> EngineHandle:
        return self._ensure(EngineKind.VISION)

    def reasoner(self) -> EngineHandle:
        return self._ensure(EngineKind.REASONER)

    def shutdown(self) -> None:
        with self._lock:
            for h in self._handles.values():
                h.stop()
            self._handles.clear()

    # ---- internals ----

    def _ensure(self, kind: str) -> EngineHandle:
        with self._lock:
            existing = self._handles.get(kind)
            if existing and existing.proc.poll() is None:
                return existing
            h = self._spawn(kind)
            self._handles[kind] = h
            return h

    def _binary_path(self) -> Path:
        path = self.paths.engine_dir / ENGINE_BINARY
        if not path.exists():
            raise FileNotFoundError(
                f"AI engine binary not present at {path}. "
                "Run scripts/install-engine.sh (developer mode) or reinstall the app."
            )
        return path

    def _spec_for(self, kind: str) -> EngineSpec:
        return self.manifest.vision() if kind == EngineKind.VISION else self.manifest.reasoner()

    def _build_args(self, kind: str, port: int) -> list[str]:
        engine = self._binary_path()
        spec = self._spec_for(kind)
        model = self.paths.engine_dir / spec.model_file
        args = [
            str(engine),
            "--model", str(model),
            "--port", str(port),
            "--host", "127.0.0.1",
            "--n-gpu-layers", "999",
        ]
        if kind == EngineKind.VISION:
            if not spec.mmproj_file:
                raise RuntimeError(f"{spec.display_name} manifest entry has no mmproj_file")
            args.extend(["--mmproj", str(self.paths.engine_dir / spec.mmproj_file)])
            args.extend(["--ctx-size", "8192"])
        else:
            args.extend(["--ctx-size", "16384"])
        return args

    @staticmethod
    def _port_is_free(port: int) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return True
            except OSError:
                return False

    def _spawn(self, kind: str) -> EngineHandle:
        port = VISION_PORT if kind == EngineKind.VISION else REASONER_PORT
        if not self._port_is_free(port):
            # Try a +10 fallback to avoid collisions in dev.
            port += 10
        args = self._build_args(kind, port)
        spec = self._spec_for(kind)
        env = dict(os.environ)
        # Silence the engine binary's verbose startup banner. The env var name is
        # the binary's own; it has no effect outside the subprocess.
        env.setdefault("LLAMA_NO_LOG", "1")

        log.info("starting %s (%s v%s) on port %s", kind, spec.display_name, spec.version, port)
        proc = subprocess.Popen(  # noqa: S603 — args come from our own paths.
            args,
            stdout=subprocess.DEVNULL if not os.environ.get("DMS_DEBUG") else sys.stderr,
            stderr=subprocess.DEVNULL if not os.environ.get("DMS_DEBUG") else sys.stderr,
            env=env,
            close_fds=True,
        )
        base_url = f"http://127.0.0.1:{port}"

        # Wait for /health to respond — vision model loads can take 15+ seconds.
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                raise RuntimeError(f"{kind} engine exited with code {proc.returncode}")
            try:
                r = httpx.get(f"{base_url}/health", timeout=2.0)
                if r.status_code == 200:
                    return EngineHandle(kind=kind, port=port, base_url=base_url, proc=proc)
            except httpx.HTTPError:
                pass
            time.sleep(0.5)

        proc.terminate()
        raise TimeoutError(f"{kind} engine never reached /health within 120 s")
