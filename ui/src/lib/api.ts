// ---------- runtime adapter ----------
// The UI is web-only. At build time `VITE_DMS_BASE_URL` + `VITE_DMS_TOKEN` are
// baked in (Vercel env vars). For `pnpm dev` against a locally-running sidecar
// we fall back to reading the handshake JSON written by scripts/dev-browser.sh.

declare global {
  interface Window {
    __DMS_DEV__?: { baseUrl: string; token: string };
  }
}

type Endpoint = { baseUrl: string; token: string };

async function getEndpoint(): Promise<Endpoint> {
  const envBase = import.meta.env.VITE_DMS_BASE_URL as string | undefined;
  const envTok = import.meta.env.VITE_DMS_TOKEN as string | undefined;
  if (envBase && envTok) {
    return { baseUrl: envBase, token: envTok };
  }
  if (typeof window !== "undefined" && window.__DMS_DEV__) {
    return window.__DMS_DEV__;
  }
  // Dev fallback: read sidecar handshake from /_dms_dev_handshake.json (served by Vite).
  if (typeof window !== "undefined") {
    try {
      const r = await fetch("/_dms_dev_handshake.json");
      if (r.ok) {
        const j = await r.json();
        const endpoint = {
          baseUrl: `http://127.0.0.1:${j.port}`,
          token: j.token as string,
        };
        window.__DMS_DEV__ = endpoint;
        return endpoint;
      }
    } catch {
      // fall through
    }
  }
  throw new Error("sidecar endpoint is not configured (set VITE_DMS_BASE_URL + VITE_DMS_TOKEN)");
}

type Method = "GET" | "POST" | "PUT" | "DELETE";

async function api<T = unknown>(
  method: Method,
  path: string,
  body?: unknown,
  opts: { form?: FormData } = {}
): Promise<T> {
  const { baseUrl, token } = await getEndpoint();
  const url = `${baseUrl}${path}`;
  const init: RequestInit = {
    method,
    headers: {
      Authorization: `Bearer ${token}`,
    },
  };
  if (opts.form) {
    init.body = opts.form;
  } else if (method !== "GET" && body !== undefined) {
    (init.headers as Record<string, string>)["Content-Type"] = "application/json";
    init.body = JSON.stringify(body);
  }

  const r = await fetch(url, init);
  if (!r.ok) {
    let detail = "";
    try {
      detail = await r.text();
    } catch {
      /* ignore */
    }
    throw new Error(`sidecar ${r.status}: ${path}: ${detail}`);
  }
  if (method === "DELETE" && r.status === 204) return undefined as T;
  const ct = r.headers.get("content-type") || "";
  if (ct.includes("application/json")) return r.json();
  return r.text() as unknown as T;
}

// ---------- types ----------

export type JobStatus =
  | "pending"
  | "fetching"
  | "parsing"
  | "organizing"
  | "filing"
  | "done"
  | "partial"
  | "failed"
  | "cancelled";

export interface JobStats {
  fetched?: number;
  parsed?: number;
  filed?: number;
  skipped?: number;
  errors?: number;
}

export interface Job {
  job_id: string;
  status: JobStatus;
  stats: JobStats | null;
  error_message: string | null;
  started_at: number;
  finished_at: number | null;
}

export interface JobRow {
  id: string;
  status: JobStatus;
  trigger: string;
  started_at: number;
  finished_at: number | null;
  stats_json: string | null;
  error_message: string | null;
  destination_folder: string | null;
}

export interface DocumentRow {
  id: string;
  job_id: string;
  original_name: string;
  status: string;
  final_path: string | null;
  parsed_metadata_json: string | null;
  error_message: string | null;
}

export interface AppPaths {
  app_data: string;
  local_data: string;
  engine_dir: string;
  organized_root: string;
}

export interface Taxonomy {
  entities: string[];
  document_types: { name: string; canonical_folder: string }[];
  versions: { document_type: string; version_label: string }[];
}

export interface UploadResult {
  job_id: string;
  accepted: number;
  rejected: { name: string; reason: string }[];
}

// ---------- calls ----------

export async function uploadFiles(files: File[]): Promise<UploadResult> {
  const form = new FormData();
  for (const f of files) form.append("files", f, f.name);
  form.append("trigger", "upload");
  return api<UploadResult>("POST", "/runs/upload", undefined, { form });
}

export async function getJob(jobId: string): Promise<Job> {
  return api("GET", `/jobs/${jobId}`);
}

export async function listJobs(): Promise<JobRow[]> {
  return api("GET", "/jobs");
}

export async function cancelJob(
  jobId: string
): Promise<{ cancelled: boolean; status?: string; reason?: string }> {
  return api("POST", `/jobs/${jobId}/cancel`, {});
}

export async function deleteJob(
  jobId: string
): Promise<{ deleted: boolean; files_removed: number }> {
  return api("DELETE", `/jobs/${jobId}`);
}

export async function listJobDocuments(jobId: string): Promise<DocumentRow[]> {
  return api("GET", `/jobs/${jobId}/documents`);
}

export interface ParseLogRecord {
  doc_id?: string;
  original_name?: string;
  document_type?: string | null;
  version?: string | null;
  date?: string | null;
  person_name?: string | null;
  entity_name?: string | null;
  confidence?: number;
  [key: string]: unknown;
}

export async function getJobLog(jobId: string): Promise<ParseLogRecord[]> {
  return api("GET", `/jobs/${jobId}/log`);
}

export interface LogRecord {
  ts?: string;
  level?: string;
  logger?: string;
  msg?: string;
  extra?: Record<string, unknown>;
  exc?: string;
  raw?: string;
}

export async function getRecentLog(limit = 200): Promise<LogRecord[]> {
  return api("GET", `/logs/recent?limit=${limit}`);
}

export async function getPaths(): Promise<AppPaths> {
  return api("GET", "/paths");
}

export async function getTaxonomy(): Promise<Taxonomy> {
  return api("GET", "/taxonomy");
}

export async function getDocumentSignedUrl(
  docId: string
): Promise<{ url: string }> {
  return api("GET", `/documents/${docId}/signed_url`);
}

export interface BrowseEntry {
  name: string;
  is_folder: boolean;
  size?: number | null;
  updated_at?: string | null;
  content_type?: string | null;
  // Enriched fields (files only; populated when the row matches a `documents`
  // record by final_path).
  doc_id?: string;
  document_type?: string | null;
  entity_name?: string | null;
  person_name?: string | null;
  date?: string | null;
  version?: string | null;
  confidence?: number | null;
  status?: string;
  original_name?: string;
  job_id?: string;
  modality?: "image" | "text" | null;
  transcript_key?: string | null;
}

export interface BrowseResponse {
  prefix: string;
  entries: BrowseEntry[];
}

export interface DashboardStats {
  total_documents: number;
  filed_this_week: number;
  filed_prev_week: number;
  types_used: number;
  entities_used: number;
  top_types: { type: string; count: number }[];
  top_entities: { entity: string; count: number }[];
  modality_breakdown: { modality: string; count: number }[];
  recent_uploads: {
    id: string;
    original_name: string;
    final_path: string | null;
    parsed_metadata_json: string | null;
    filed_at: number | null;
    job_id: string;
  }[];
}

export async function getDashboardStats(): Promise<DashboardStats> {
  return api("GET", "/dashboard/stats");
}

export async function browse(prefix: string): Promise<BrowseResponse> {
  const qs = prefix ? `?prefix=${encodeURIComponent(prefix)}` : "";
  return api("GET", `/browse${qs}`);
}

export async function getOrganizedSignedUrl(
  key: string
): Promise<{ url: string }> {
  return api("GET", `/browse/signed_url?key=${encodeURIComponent(key)}`);
}

/** Open any object in the organized bucket via short-lived signed URL. */
export async function openOrganizedKey(key: string): Promise<void> {
  const { url } = await getOrganizedSignedUrl(key);
  window.open(url, "_blank", "noopener");
}

/** Open a filed document in a new browser tab via short-lived signed URL. */
export async function openDocument(docId: string): Promise<void> {
  const { url } = await getDocumentSignedUrl(docId);
  window.open(url, "_blank", "noopener");
}

/** Convenience for arbitrary outbound links (no sidecar round-trip). */
export function openUrl(url: string): void {
  window.open(url, "_blank", "noopener");
}

export async function getDestinationRoot(): Promise<{ destination_root: string | null }> {
  return api("GET", "/settings/destination_root");
}

export async function setDestinationRoot(
  destinationRoot: string | null
): Promise<{ destination_root: string | null }> {
  return api("PUT", "/settings/destination_root", { destination_root: destinationRoot });
}

export async function previewDestination(): Promise<{ destination: string }> {
  return api("GET", "/settings/destination_root/preview");
}
