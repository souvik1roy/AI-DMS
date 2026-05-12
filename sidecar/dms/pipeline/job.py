from __future__ import annotations

import json
import logging
import shutil
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import ulid

from dms.config import (
    APP_CONFIG_DESTINATION_ROOT,
    ORGANIZED_BUCKET,
    Paths,
    STAGING_BUCKET,
    resolve_destination,
)
from dms.connectors.local_folder import StagedDoc
from dms.db.repo import Repo
from dms.pipeline.extractors import extract
from dms.pipeline.filer import clear_folder_cache, file_into_place, teardown_run
from dms.pipeline.vision import parse_doc
from dms.storage import supabase_store

log = logging.getLogger("dms.job")


@dataclass
class _RuntimeDoc:
    """The orchestrator's view of a staged document inside the pipeline."""

    doc_id: str
    original_name: str
    source_ref: str
    staging_key: str
    content_hash: str
    suffix: str


class JobCancelled(RuntimeError):
    pass


class JobOrchestrator:
    def __init__(self, paths: Paths, repo: Repo) -> None:
        self.paths = paths
        self.repo = repo
        self._cancel_events: dict[str, threading.Event] = {}
        self._cancel_lock = threading.Lock()

    # ---------- cancellation ----------

    def request_cancel(self, job_id: str) -> bool:
        with self._cancel_lock:
            ev = self._cancel_events.get(job_id)
        if ev is None:
            return False
        ev.set()
        return True

    def _register_cancel_token(self, job_id: str) -> threading.Event:
        ev = threading.Event()
        with self._cancel_lock:
            self._cancel_events[job_id] = ev
        return ev

    def _clear_cancel_token(self, job_id: str) -> None:
        with self._cancel_lock:
            self._cancel_events.pop(job_id, None)

    @staticmethod
    def _check_cancel(ev: threading.Event) -> None:
        if ev.is_set():
            raise JobCancelled()

    # ---------- lifecycle ----------

    def shutdown(self) -> None:
        # Nothing process-level to tear down in the web build (no engine subprocesses).
        return None

    # ---------- public ----------

    def create_job(
        self,
        connection_id: int | None,
        trigger: str = "manual",
        destination_folder: str | None = None,
    ) -> str:
        job_id = ulid.new().str
        run_dir = self.paths.runs_dir / job_id
        run_dir.mkdir(parents=True, exist_ok=True)
        log_path = run_dir / "parse.jsonl"
        log_path.touch(exist_ok=True)

        # Resolve the destination prefix at create-time so it's persisted with the job.
        global_default = self.repo.get_config(APP_CONFIG_DESTINATION_ROOT)
        destination = resolve_destination(
            requested=destination_folder,
            global_default=global_default,
            job_id=job_id,
        )

        self.repo.insert_job(
            job_id=job_id,
            connection_id=connection_id,
            run_dir=run_dir,
            log_path=log_path,
            trigger=trigger,
            destination_folder=destination,
        )
        return job_id

    def run_uploaded_job(self, job_id: str, staged: list[StagedDoc]) -> None:
        """Pipeline entrypoint when documents arrive via HTTP upload (already in
        the `staging` bucket; their hashes were computed during upload).
        """
        runtime = [
            _RuntimeDoc(
                doc_id=s.doc_id,
                original_name=s.original_name,
                source_ref=s.source_ref,
                staging_key=s.staging_key,
                content_hash=s.content_hash,
                suffix=s.suffix,
            )
            for s in staged
        ]
        self._run(job_id, runtime)

    # ---------- shared pipeline ----------

    def _run(self, job_id: str, staged: list[_RuntimeDoc]) -> None:
        run_dir = self.paths.runs_dir / job_id
        run_dir.mkdir(parents=True, exist_ok=True)
        log_path = run_dir / "parse.jsonl"
        log_path.touch(exist_ok=True)

        stats: dict[str, Any] = {"fetched": 0, "parsed": 0, "filed": 0, "skipped": 0, "errors": 0}
        cancel_ev = self._register_cancel_token(job_id)

        try:
            # ---- 1. record staged documents + dedupe by content hash ----
            self.repo.update_job_status(job_id, "fetching")
            kept: list[_RuntimeDoc] = []
            for doc in staged:
                self._check_cancel(cancel_ev)
                self.repo.insert_document(
                    doc_id=doc.doc_id,
                    job_id=job_id,
                    original_name=doc.original_name,
                    staging_path=doc.staging_key,
                    source_ref=doc.source_ref,
                )
                self.repo.set_document_hash(doc.doc_id, doc.content_hash)
                if self.repo.has_hash_in_other_job(doc.content_hash, job_id):
                    self.repo.set_document_skipped(
                        doc.doc_id, "duplicate of previously filed doc"
                    )
                    try:
                        supabase_store.delete(STAGING_BUCKET, doc.staging_key)
                    except Exception:  # noqa: BLE001
                        log.exception("failed to delete duplicate staging object")
                    stats["skipped"] += 1
                    continue
                kept.append(doc)
                stats["fetched"] += 1
            self.repo.update_job_status(job_id, "fetching", stats=stats)

            if not kept:
                self.repo.update_job_status(job_id, "done", stats=stats, finished=True)
                teardown_run(job_id)
                return

            # ---- 2 + 3. extract per-modality + classify via OpenAI ----
            self.repo.update_job_status(job_id, "parsing", stats=stats)
            parse_lines: list[str] = []
            metadata_by_doc_id: dict[str, dict[str, Any]] = {}
            transcript_by_doc_id: dict[str, bytes] = {}
            for doc in kept:
                self._check_cancel(cancel_ev)
                try:
                    body = supabase_store.download(STAGING_BUCKET, doc.staging_key)
                    parse_input = extract(
                        body=body,
                        suffix=doc.suffix,
                        job_id=job_id,
                        doc_id=doc.doc_id,
                    )
                    metadata = parse_doc(parse_input)
                    metadata["doc_id"] = doc.doc_id
                    metadata["original_name"] = doc.original_name
                    metadata["modality"] = parse_input.modality
                    if parse_input.extraction_note:
                        metadata["extraction"] = parse_input.extraction_note
                    if parse_input.transcript_full:
                        transcript_by_doc_id[doc.doc_id] = parse_input.transcript_full
                    line = json.dumps(metadata, ensure_ascii=False)
                    parse_lines.append(line)
                    metadata_by_doc_id[doc.doc_id] = metadata
                    with log_path.open("a", encoding="utf-8") as f:
                        f.write(line + "\n")
                    self.repo.set_document_parsed(doc.doc_id, metadata)
                    stats["parsed"] += 1
                    self.repo.update_job_status(job_id, "parsing", stats=stats)
                except Exception as e:  # noqa: BLE001
                    log.exception("parse failed for %s", doc.staging_key)
                    self.repo.set_document_failed(doc.doc_id, f"parse: {e}")
                    stats["errors"] += 1

            if not parse_lines:
                self.repo.update_job_status(
                    job_id, "failed", stats=stats, error="no documents parsed", finished=True
                )
                return

            # ---- 4. file each doc using deterministic path from vision metadata ----
            # Path is AI-DMS/<DocumentType>/<EntityOrPerson>/<original_name>.
            # No reasoner LLM call — `compute_final_key` in filer.py owns the path logic.
            self.repo.update_job_status(job_id, "filing", stats=stats)
            clear_folder_cache()  # fresh view of bucket subfolders for this job
            for doc in kept:
                self._check_cancel(cancel_ev)
                meta = metadata_by_doc_id.get(doc.doc_id)
                if meta is None:
                    # Doc never parsed successfully — skip filing.
                    continue
                try:
                    final_key = file_into_place(
                        staging_key=doc.staging_key,
                        document_type=meta.get("document_type"),
                        entity_name=meta.get("entity_name"),
                        person_name=meta.get("person_name"),
                        original_name=doc.original_name,
                        expected_hash=doc.content_hash,
                    )
                    # Persist a sidecar transcript next to audio/video/csv/txt.
                    transcript = transcript_by_doc_id.get(doc.doc_id)
                    if transcript:
                        sidecar_key = f"{final_key}.transcript.txt"
                        try:
                            supabase_store.upload(
                                ORGANIZED_BUCKET,
                                sidecar_key,
                                transcript,
                                content_type="text/plain; charset=utf-8",
                            )
                            meta["transcript_key"] = sidecar_key
                            self.repo.set_document_parsed(doc.doc_id, meta)
                        except Exception:  # noqa: BLE001
                            log.exception(
                                "transcript upload failed",
                                extra={"sidecar_key": sidecar_key},
                            )
                    self.repo.set_document_filed(doc.doc_id, final_key)
                    raw_owner = (
                        (meta.get("entity_name") or meta.get("person_name") or "").strip()
                    )
                    if raw_owner:
                        try:
                            self.repo.upsert_entity(raw_owner)
                        except Exception:  # noqa: BLE001
                            log.exception("upsert_entity failed", extra={"entity": raw_owner})
                    stats["filed"] += 1
                    self.repo.update_job_status(job_id, "filing", stats=stats)
                except Exception as e:  # noqa: BLE001
                    log.exception("file failed for %s", doc.staging_key)
                    self.repo.set_document_failed(doc.doc_id, f"file: {e}")
                    stats["errors"] += 1

            # ---- 5. archive parse log + cleanup staging ----
            clear_folder_cache()
            self._archive_parse_log(job_id, log_path)
            teardown_run(job_id)

            self.repo.update_job_status(job_id, "done", stats=stats, finished=True)
            log.info("job done", extra={"job_id": job_id, "stats": stats})

        except JobCancelled:
            log.info("job cancelled", extra={"job_id": job_id, "stats": stats})
            self.repo.update_job_status(
                job_id,
                "cancelled",
                stats=stats,
                error="cancelled by user",
                finished=True,
            )
            self._archive_parse_log(job_id, log_path)
            try:
                teardown_run(job_id)
            except Exception:  # noqa: BLE001
                pass
        except Exception as e:  # noqa: BLE001
            log.exception("job %s crashed", job_id, extra={"job_id": job_id})
            self.repo.update_job_status(
                job_id, "failed", stats=stats, error=str(e), finished=True
            )
            self._archive_parse_log(job_id, log_path)
        finally:
            self._clear_cancel_token(job_id)

    def _archive_parse_log(self, job_id: str, log_path: Path) -> None:
        """Copy the per-job parse.jsonl into <tmp>/logs/jobs/<job_id>.jsonl."""
        if not log_path.exists() or log_path.stat().st_size == 0:
            return
        try:
            target = self.paths.job_logs_dir / f"{job_id}.jsonl"
            shutil.copy2(log_path, target)
        except OSError:
            log.exception("could not archive parse log", extra={"job_id": job_id})
