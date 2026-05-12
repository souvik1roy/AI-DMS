"""Engine manifest loader.

Reads `engine/engine.json` written by `scripts/install_engine.py`. The manifest
is the only contract between install-time and runtime — model family identifiers
never appear here; only the public cover names ("OpenGraph Vision",
"OpenGraph Text") and opaque local filenames.

If the manifest is missing (older install or pre-bundled dev tree without a
recipe run yet) we fall back to the legacy constants in `dms.config` and a
generic display name so the rest of the pipeline keeps working.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

from dms.config import REASONER_MODEL_FILE, VISION_MODEL_FILE, VISION_PROJECTOR_FILE

log = logging.getLogger("dms.engine")

MANIFEST_FILENAME = "engine.json"


@dataclass(frozen=True)
class EngineSpec:
    id: str
    display_name: str
    version: str
    model_file: str
    mmproj_file: str | None
    runtime_name: str
    runtime_version: str


class EngineManifestError(RuntimeError):
    pass


class EngineManifest:
    """Lightweight read-only view over engine/engine.json."""

    def __init__(self, engine_dir: Path, payload: dict) -> None:
        self.engine_dir = engine_dir
        self._payload = payload

    @classmethod
    def load(cls, engine_dir: Path) -> "EngineManifest":
        path = engine_dir / MANIFEST_FILENAME
        if path.exists():
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as e:
                raise EngineManifestError(f"engine manifest is not valid JSON: {e}") from e
            if not isinstance(payload, dict) or "engines" not in payload:
                raise EngineManifestError("engine manifest missing required 'engines' field")
            log.debug("loaded engine manifest from %s", path)
            return cls(engine_dir, payload)

        # Fallback: synthesize a minimal manifest from the legacy filename constants.
        log.debug("no engine manifest at %s; using fallback spec", path)
        fallback = {
            "schema_version": 1,
            "runtime": {"name": "ai-engine-core", "version": "unknown"},
            "engines": {
                "vision": {
                    "display_name": "AI engine",
                    "version": "0.0.0",
                    "model_file": VISION_MODEL_FILE,
                    "mmproj_file": VISION_PROJECTOR_FILE,
                },
                "reasoner": {
                    "display_name": "AI engine",
                    "version": "0.0.0",
                    "model_file": REASONER_MODEL_FILE,
                },
            },
        }
        return cls(engine_dir, fallback)

    # ---------- accessors ----------

    @property
    def runtime_name(self) -> str:
        return str(self._payload.get("runtime", {}).get("name", "ai-engine-core"))

    @property
    def runtime_version(self) -> str:
        return str(self._payload.get("runtime", {}).get("version", "unknown"))

    def _spec(self, key: str) -> EngineSpec:
        engines = self._payload.get("engines", {})
        entry = engines.get(key)
        if not entry:
            raise EngineManifestError(f"engine '{key}' missing from manifest")
        model_file = entry.get("model_file")
        if not model_file:
            raise EngineManifestError(f"engine '{key}' has no model_file in manifest")
        return EngineSpec(
            id=key,
            display_name=str(entry.get("display_name") or "AI engine"),
            version=str(entry.get("version") or "0.0.0"),
            model_file=str(model_file),
            mmproj_file=entry.get("mmproj_file") or None,
            runtime_name=self.runtime_name,
            runtime_version=self.runtime_version,
        )

    def vision(self) -> EngineSpec:
        return self._spec("vision")

    def reasoner(self) -> EngineSpec:
        return self._spec("reasoner")

    def validate_files_present(self) -> list[str]:
        """Return a list of missing-file errors. Empty list means everything is ready."""
        missing: list[str] = []
        for spec in (self.vision(), self.reasoner()):
            mp = self.engine_dir / spec.model_file
            if not mp.exists():
                missing.append(f"{spec.display_name}: model file not found at {mp}")
            if spec.mmproj_file:
                pp = self.engine_dir / spec.mmproj_file
                if not pp.exists():
                    missing.append(
                        f"{spec.display_name}: companion file not found at {pp}"
                    )
        return missing
