from __future__ import annotations

import asyncio
import json as _json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import ulid
from fastapi import (
    Depends,
    FastAPI,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from dms.config import (
    APP_CONFIG_DESTINATION_ROOT,
    ORGANIZED_BUCKET,
    SIGNED_URL_TTL_SECONDS,
    STAGING_BUCKET,
    Paths,
    default_destination_for_job,
)
from dms.connectors.local_folder import (
    StagedDoc,
    is_supported,
    stage_bytes,
)
from dms.db.repo import Repo
from dms.pipeline.job import JobOrchestrator
from dms.storage import supabase_store

logger = logging.getLogger("dms")
logger.setLevel(logging.INFO)


class DestinationRootRequest(BaseModel):
    destination_root: str | None = Field(
        default=None,
        description="Key prefix inside the organized bucket, or null to clear.",
    )


class JobStateResponse(BaseModel):
    job_id: str
    status: str
    stats: dict[str, Any] | None = None
    error_message: str | None = None
    started_at: int
    finished_at: int | None = None


def _require_bearer(token: str):
    async def _dep(request: Request) -> None:
        auth = request.headers.get("authorization", "")
        if not auth.startswith("Bearer ") or auth.removeprefix("Bearer ").strip() != token:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="bad token")

    return _dep


def _allowed_origins() -> list[str]:
    """Comma-separated `WEB_ORIGIN` env var; defaults to a dev origin."""
    raw = os.environ.get("WEB_ORIGIN", "").strip()
    if not raw:
        return ["http://localhost:5173", "http://127.0.0.1:5173"]
    return [o.strip() for o in raw.split(",") if o.strip()]


def create_app(token: str) -> FastAPI:
    paths = Paths.resolve()
    repo = Repo()
    orchestrator = JobOrchestrator(paths=paths, repo=repo)

    app = FastAPI(title="AI DMS", version="0.2.0", docs_url=None, redoc_url=None)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_allowed_origins(),
        allow_methods=["*"],
        allow_headers=["*"],
    )

    auth = _require_bearer(token)

    # ---------- health / paths / taxonomy ----------

    @app.get("/health")
    async def health() -> dict[str, Any]:
        return {"ok": True, "version": "0.2.0"}

    @app.get("/paths", dependencies=[Depends(auth)])
    async def get_paths() -> dict[str, str]:
        # Field names preserved for UI compatibility; values are now Supabase URIs.
        return {
            "app_data": f"supabase://{STAGING_BUCKET}",
            "local_data": f"supabase://{STAGING_BUCKET}",
            "engine_dir": "openai://chat/completions",
            "organized_root": f"supabase://{ORGANIZED_BUCKET}",
        }

    @app.get("/taxonomy", dependencies=[Depends(auth)])
    async def taxonomy() -> dict[str, Any]:
        return repo.snapshot_taxonomy()

    # ---------- jobs ----------

    @app.get("/jobs", dependencies=[Depends(auth)])
    async def list_jobs() -> list[dict[str, Any]]:
        return repo.list_jobs()

    @app.get("/jobs/{job_id}", dependencies=[Depends(auth)])
    async def get_job(job_id: str) -> JobStateResponse:
        job = repo.get_job(job_id)
        if not job:
            raise HTTPException(404, "job not found")
        stats = _json.loads(job["stats_json"]) if job.get("stats_json") else None
        return JobStateResponse(
            job_id=job["id"],
            status=job["status"],
            stats=stats,
            error_message=job.get("error_message"),
            started_at=job["started_at"],
            finished_at=job.get("finished_at"),
        )

    @app.get("/jobs/{job_id}/documents", dependencies=[Depends(auth)])
    async def list_job_documents(job_id: str) -> list[dict[str, Any]]:
        return repo.list_documents_for_job(job_id)

    @app.post("/jobs/{job_id}/cancel", dependencies=[Depends(auth)])
    async def cancel_job(job_id: str) -> dict[str, Any]:
        job = repo.get_job(job_id)
        if not job:
            raise HTTPException(404, "job not found")
        if job["status"] in ("done", "failed", "partial", "cancelled"):
            return {"cancelled": False, "reason": f"job already {job['status']}"}
        signalled = orchestrator.request_cancel(job_id)
        return {"cancelled": signalled, "status": job["status"]}

    @app.delete("/jobs/{job_id}", dependencies=[Depends(auth)])
    async def delete_job(job_id: str) -> dict[str, Any]:
        """Delete a finished job: removes filed-document objects from the organized
        bucket and the staging bucket, then deletes the DB rows. Never deletes the
        bucket itself.
        """
        job = repo.get_job(job_id)
        if not job:
            raise HTTPException(404, "job not found")
        if job["status"] in ("pending", "fetching", "parsing", "organizing", "filing"):
            raise HTTPException(409, "job is still running; cancel it first")

        removed_files = 0
        for doc in repo.list_documents_for_job(job_id):
            fp = doc.get("final_path")
            if not fp:
                continue
            try:
                supabase_store.delete(ORGANIZED_BUCKET, fp)
                removed_files += 1
            except Exception:  # noqa: BLE001
                logger.exception("could not delete %s", fp)
            # Also drop any sidecar transcript that lives next to the file.
            md_raw = doc.get("parsed_metadata_json")
            sidecar_key: str | None = None
            if md_raw:
                try:
                    md = _json.loads(md_raw)
                    sidecar_key = md.get("transcript_key")
                except (TypeError, ValueError):
                    sidecar_key = None
            if not sidecar_key:
                sidecar_key = f"{fp}.transcript.txt"
            try:
                supabase_store.delete(ORGANIZED_BUCKET, sidecar_key)
            except Exception:  # noqa: BLE001
                pass  # sidecar may not exist — that's fine

        # Best-effort cleanup of any staging leftovers (e.g. cancelled jobs).
        try:
            supabase_store.delete_prefix(STAGING_BUCKET, job_id)
        except Exception:  # noqa: BLE001
            logger.exception("could not delete staging prefix for %s", job_id)

        repo.delete_job(job_id)
        return {"deleted": True, "files_removed": removed_files}

    @app.get("/jobs/{job_id}/log", dependencies=[Depends(auth)])
    async def get_job_log(job_id: str) -> list[dict[str, Any]]:
        """Return the archived parse.jsonl as a list of parsed records."""
        path = paths.job_logs_dir / f"{job_id}.jsonl"
        if not path.exists():
            raise HTTPException(404, "no archived log for this job")
        records: list[dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                records.append(_json.loads(line))
            except _json.JSONDecodeError:
                records.append({"raw": line})
        return records

    @app.get("/logs/recent", dependencies=[Depends(auth)])
    async def get_recent_log(limit: int = 200) -> list[dict[str, Any]]:
        """Return the tail of today's sidecar log as a list of parsed records."""
        limit = max(1, min(limit, 2000))
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        path = paths.logs_dir / f"sidecar-{today}.jsonl"
        if not path.exists():
            return []
        try:
            lines = path.read_text(encoding="utf-8").splitlines()[-limit:]
        except OSError as e:
            raise HTTPException(500, f"could not read logs: {e}") from e
        records: list[dict[str, Any]] = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(_json.loads(line))
            except _json.JSONDecodeError:
                records.append({"raw": line})
        return records

    @app.post("/runs/upload", dependencies=[Depends(auth)])
    async def runs_upload(
        files: list[UploadFile] = File(...),
        destination_folder: str | None = Form(default=None),
        trigger: str = Form(default="upload"),
    ) -> dict[str, Any]:
        """Browser drag-and-drop entrypoint. Streams each file into the staging
        bucket, records it in the DB, then kicks off the orchestrator on a
        worker thread.
        """
        accepted: list[StagedDoc] = []
        rejected: list[dict[str, str]] = []

        job_id = orchestrator.create_job(
            connection_id=None,
            trigger=trigger,
            destination_folder=destination_folder,
        )

        for f in files:
            name = f.filename or "unnamed"
            if not is_supported(name):
                rejected.append({"name": name, "reason": "unsupported file type"})
                continue
            data = await f.read()
            if not data:
                rejected.append({"name": name, "reason": "empty file"})
                continue
            doc_id = ulid.new().str
            staged = await asyncio.to_thread(
                stage_bytes,
                data=data,
                original_name=name,
                job_id=job_id,
                doc_id=doc_id,
                source_ref=f"upload:{name}",
                content_type=f.content_type or "application/octet-stream",
            )
            accepted.append(staged)

        if not accepted:
            repo.update_job_status(
                job_id,
                "failed",
                error="no eligible files in upload",
                finished=True,
            )
            return {"job_id": job_id, "accepted": 0, "rejected": rejected}

        asyncio.create_task(
            asyncio.to_thread(orchestrator.run_uploaded_job, job_id, accepted)
        )
        return {"job_id": job_id, "accepted": len(accepted), "rejected": rejected}

    @app.get("/browse", dependencies=[Depends(auth)])
    async def browse(prefix: str = "") -> dict[str, Any]:
        """Folder-style listing of the organised bucket. `prefix` is the path
        under the bucket (no leading slash). Returns the immediate children
        (folders + files) at that prefix; file entries are enriched with the
        parsed metadata stored in Postgres (when available).
        """
        prefix_clean = prefix.strip("/")
        entries = await asyncio.to_thread(
            supabase_store.list_children, ORGANIZED_BUCKET, prefix_clean
        )

        # Bulk-fetch document rows for any file entries so the UI can show
        # parsed metadata (entity, doc type, date, confidence) inline.
        file_keys = [
            f"{prefix_clean}/{e['name']}" if prefix_clean else e["name"]
            for e in entries
            if not e["is_folder"]
        ]
        meta_by_key = repo.get_documents_by_final_paths(file_keys) if file_keys else {}
        for e in entries:
            if e["is_folder"]:
                continue
            key = f"{prefix_clean}/{e['name']}" if prefix_clean else e["name"]
            doc = meta_by_key.get(key)
            if not doc:
                continue
            md_raw = doc.get("parsed_metadata_json")
            md: dict[str, Any] = {}
            if md_raw:
                try:
                    md = _json.loads(md_raw)
                except (TypeError, ValueError):
                    md = {}
            e["doc_id"] = doc["id"]
            e["document_type"] = md.get("document_type")
            e["entity_name"] = md.get("entity_name")
            e["person_name"] = md.get("person_name")
            e["date"] = md.get("date")
            e["version"] = md.get("version")
            e["confidence"] = md.get("confidence")
            e["status"] = doc.get("status")
            e["original_name"] = doc.get("original_name")
            e["job_id"] = doc.get("job_id")
            e["modality"] = md.get("modality")
            e["transcript_key"] = md.get("transcript_key")

        return {"prefix": prefix_clean, "entries": entries}

    @app.get("/dashboard/stats", dependencies=[Depends(auth)])
    async def dashboard_stats() -> dict[str, Any]:
        return await asyncio.to_thread(repo.dashboard_stats)

    @app.post("/admin/seed-taxonomy", dependencies=[Depends(auth)])
    async def admin_seed_taxonomy() -> dict[str, Any]:
        """Ensure one top-level folder exists in the organised bucket for each
        of the 100 allowed document types. Idempotent — only uploads `.keep`
        for types that don't already have one.
        """
        from dms.llm.prompts import ALLOWED_DOCUMENT_TYPES
        from dms.pipeline.filer import _sanitize_segment

        def _seed() -> tuple[int, int, list[dict[str, str]]]:
            created = 0
            existed = 0
            errors: list[dict[str, str]] = []
            for type_name in ALLOWED_DOCUMENT_TYPES:
                folder = _sanitize_segment(type_name)
                key = f"{folder}/.keep"
                try:
                    if supabase_store.exists(ORGANIZED_BUCKET, key):
                        existed += 1
                        continue
                    supabase_store.upload(
                        ORGANIZED_BUCKET,
                        key,
                        b"# Marker so the folder is visible in Browse before any docs land here.\n",
                        content_type="text/plain",
                    )
                    created += 1
                except Exception as e:  # noqa: BLE001
                    errors.append({"type": type_name, "error": str(e)})
            return created, existed, errors

        created, existed, errors = await asyncio.to_thread(_seed)
        return {"created": created, "existed": existed, "errors": errors}

    @app.get("/browse/signed_url", dependencies=[Depends(auth)])
    async def browse_signed_url(key: str) -> dict[str, str]:
        """Signed URL for any object key under the organized bucket — used by
        the Browse tab when the user clicks a file that may not have a
        document_id (e.g. legacy uploads or other apps writing into the bucket).
        """
        if not key:
            raise HTTPException(400, "key is required")
        url = supabase_store.signed_url(
            ORGANIZED_BUCKET, key.lstrip("/"), SIGNED_URL_TTL_SECONDS
        )
        return {"url": url}

    @app.get("/documents/{doc_id}/signed_url", dependencies=[Depends(auth)])
    async def document_signed_url(doc_id: str) -> dict[str, str]:
        doc = repo.get_document(doc_id)
        if not doc:
            raise HTTPException(404, "document not found")
        key = doc.get("final_path")
        if not key:
            raise HTTPException(409, "document has no final_path yet")
        url = supabase_store.signed_url(ORGANIZED_BUCKET, key, SIGNED_URL_TTL_SECONDS)
        return {"url": url}

    @app.get("/settings/destination_root", dependencies=[Depends(auth)])
    async def get_destination_root() -> dict[str, str | None]:
        return {"destination_root": repo.get_config(APP_CONFIG_DESTINATION_ROOT)}

    @app.put("/settings/destination_root", dependencies=[Depends(auth)])
    async def set_destination_root(body: DestinationRootRequest) -> dict[str, str | None]:
        if body.destination_root in (None, ""):
            repo.delete_config(APP_CONFIG_DESTINATION_ROOT)
            return {"destination_root": None}
        repo.set_config(APP_CONFIG_DESTINATION_ROOT, body.destination_root)
        return {"destination_root": body.destination_root}

    @app.get("/settings/destination_root/preview", dependencies=[Depends(auth)])
    async def preview_destination(job_id_hint: str = "<job_id>") -> dict[str, str]:
        global_default = repo.get_config(APP_CONFIG_DESTINATION_ROOT)
        if global_default:
            return {"destination": global_default}
        return {"destination": default_destination_for_job(job_id_hint)}

    # ---------- static UI (same-origin React bundle) ----------
    # When the multi-stage Docker build copies the Vite output to /app/dist,
    # we serve it from the same FastAPI app — kills the CORS class of bugs
    # and means one Render service, one URL, one deploy.
    ui_dist = Path(os.environ.get("DMS_UI_DIST", "/app/dist"))
    if ui_dist.is_dir() and (ui_dist / "index.html").is_file():
        _index_html_template = (ui_dist / "index.html").read_text(encoding="utf-8")
        _bootstrap_cfg = _json.dumps({"baseUrl": "", "token": token})
        # The UI's getEndpoint() already reads window.__DMS_DEV__ as a
        # fallback when import.meta.env.VITE_DMS_BASE_URL is unset — we
        # reuse that channel to hand the bearer token over at page load.
        _bootstrap_script = (
            f"<script>window.__DMS_DEV__={_bootstrap_cfg};</script>"
        )
        # Inject before the Vite bundle so the global is set before the
        # module evaluates. Falls back to closing </head> if Vite's output
        # ever changes shape.
        if '<script type="module"' in _index_html_template:
            _index_html = _index_html_template.replace(
                '<script type="module"',
                f'{_bootstrap_script}<script type="module"',
                1,
            )
        else:
            _index_html = _index_html_template.replace(
                "</head>", f"{_bootstrap_script}</head>", 1
            )

        if (ui_dist / "assets").is_dir():
            app.mount(
                "/assets",
                StaticFiles(directory=ui_dist / "assets"),
                name="assets",
            )

        @app.get("/", include_in_schema=False)
        async def _serve_root() -> HTMLResponse:
            return HTMLResponse(_index_html, headers={"Cache-Control": "no-cache"})

        # Catch-all for SPA client-side routing. Registered last so it
        # never shadows the API routes above.
        @app.get("/{full_path:path}", include_in_schema=False)
        async def _spa_fallback(full_path: str) -> Any:
            # If it's a real file in dist/ (favicon.ico, robots.txt, etc.),
            # serve it directly.
            candidate = ui_dist / full_path
            if candidate.is_file() and ui_dist in candidate.resolve().parents:
                return FileResponse(candidate)
            # Otherwise hand the SPA back — React Router handles the path.
            return HTMLResponse(_index_html, headers={"Cache-Control": "no-cache"})

    # ---------- lifecycle hooks ----------

    @app.on_event("shutdown")
    async def _shutdown() -> None:
        orchestrator.shutdown()

    return app
