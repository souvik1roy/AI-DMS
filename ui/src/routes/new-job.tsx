import { useState } from "react";
import { useDropzone } from "react-dropzone";
import { motion } from "framer-motion";
import { toast } from "sonner";
import { AlertCircle, Play, UploadCloud, X } from "lucide-react";
import clsx from "clsx";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { JobProgress } from "@/components/JobProgress";
import { Topbar } from "@/components/Topbar";
import { uploadFiles } from "@/lib/api";
import { iconFor } from "@/lib/file-icon";
import { prettySize } from "@/lib/format";
import { useAppStore } from "@/lib/store";

const SUPPORTED_EXTS = [
  ".pdf", ".jpg", ".jpeg", ".png", ".heic", ".tiff", ".tif", ".webp", ".gif",
  ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".odt", ".ods", ".odp",
  ".csv", ".tsv", ".txt",
  ".mp3", ".wav", ".m4a", ".ogg", ".flac", ".aac",
  ".mp4", ".mov", ".mkv", ".webm", ".avi",
];

const MODALITY_CHIPS: { label: string; ext: string; tone: "purple" | "amber" | "rose" | "emerald" | "sky" | "indigo" | "accent" }[] = [
  { label: "PDF", ext: ".pdf", tone: "accent" },
  { label: "Image", ext: ".png", tone: "purple" },
  { label: "Word", ext: ".docx", tone: "indigo" },
  { label: "Excel", ext: ".xlsx", tone: "emerald" },
  { label: "PowerPoint", ext: ".pptx", tone: "sky" },
  { label: "CSV", ext: ".csv", tone: "emerald" },
  { label: "Audio", ext: ".mp3", tone: "amber" },
  { label: "Video", ext: ".mp4", tone: "rose" },
];

function isSupported(name: string): boolean {
  const lower = name.toLowerCase();
  return SUPPORTED_EXTS.some((ext) => lower.endsWith(ext));
}

export function NewJob() {
  const [files, setFiles] = useState<File[]>([]);
  const [busy, setBusy] = useState(false);
  const activeJobId = useAppStore((s) => s.activeJobId);
  const setActiveJobId = useAppStore((s) => s.setActiveJobId);

  const eligible = files.filter((f) => isSupported(f.name));
  const skipped = files.length - eligible.length;

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop: (accepted) => {
      setFiles((prev) => {
        const seen = new Set(prev.map((f) => `${f.name}|${f.size}`));
        const merged = [...prev];
        for (const f of accepted) {
          const key = `${f.name}|${f.size}`;
          if (!seen.has(key)) {
            seen.add(key);
            merged.push(f);
          }
        }
        return merged;
      });
    },
    multiple: true,
  });

  async function onRun() {
    if (eligible.length === 0) return;
    setBusy(true);
    try {
      const { job_id, accepted, rejected } = await uploadFiles(eligible);
      setActiveJobId(job_id);
      setFiles([]);
      toast.success(`Uploaded ${accepted} file${accepted === 1 ? "" : "s"}`, {
        description:
          rejected && rejected.length
            ? `${rejected.length} rejected: ${rejected.map((r) => r.name).join(", ")}`
            : "Parsing now — track progress below.",
      });
    } catch (e) {
      toast.error("Upload failed", { description: String(e) });
    } finally {
      setBusy(false);
    }
  }

  function removeFile(idx: number) {
    setFiles((prev) => prev.filter((_, i) => i !== idx));
  }

  return (
    <div className="flex flex-col">
      <Topbar
        title="Upload"
        subtitle="Drop documents into AI-DMS"
        trailing={
          <Button
            variant="primary"
            size="sm"
            loading={busy}
            disabled={eligible.length === 0 || busy}
            leftIcon={!busy ? <Play className="h-3.5 w-3.5" /> : undefined}
            onClick={onRun}
          >
            {busy ? "Uploading…" : eligible.length > 0 ? `Organise ${eligible.length}` : "Organise"}
          </Button>
        }
      />

      <div className="mx-auto w-full max-w-3xl space-y-5 px-6 py-6">
        <header>
          <h1 className="font-display text-2xl font-semibold tracking-tight text-ink-1">
            Send documents to AI-DMS
          </h1>
          <p className="mt-1 text-sm text-ink-2">
            Each file is parsed by OpenAI, classified into one of the 100 UAE-BFSI document
            types, and filed under{" "}
            <span className="font-mono text-[12px] text-accent-ink">
              AI-DMS / &lt;DocumentType&gt; / &lt;Entity-or-Person&gt; /
            </span>
          </p>
        </header>

        <Card>
          <CardHeader title="Drop files" subtitle="PDF · images · Office · CSV · audio · video" />
          <CardBody className="pt-2">
            <div
              {...getRootProps()}
              className={clsx(
                "flex cursor-pointer flex-col items-center justify-center gap-3 rounded-card border-2 border-dashed px-6 py-12 text-center transition-colors duration-200",
                isDragActive
                  ? "border-accent bg-accent-soft"
                  : "border-border bg-canvas hover:bg-sunken"
              )}
            >
              <input {...getInputProps()} />
              <motion.div
                animate={{ scale: isDragActive ? 1.08 : 1 }}
                transition={{ type: "spring", stiffness: 400, damping: 24 }}
                className="grid h-12 w-12 place-items-center rounded-full bg-accent-soft text-accent-ink"
              >
                <UploadCloud className="h-5 w-5" />
              </motion.div>
              <div className="text-[14px] font-medium text-ink-1">
                {isDragActive ? "Drop them here" : "Drag & drop files, or click to pick"}
              </div>
              <div className="flex flex-wrap items-center justify-center gap-1">
                {MODALITY_CHIPS.map((m) => {
                  const icon = iconFor(`x${m.ext}`);
                  const Icon = icon.Icon;
                  return (
                    <Badge key={m.label} tone={m.tone} size="sm" className="gap-1">
                      <Icon className="h-3 w-3" />
                      {m.label}
                    </Badge>
                  );
                })}
              </div>
            </div>
          </CardBody>
        </Card>

        {files.length > 0 && (
          <Card>
            <CardHeader
              title={
                eligible.length > 0
                  ? `${eligible.length} file${eligible.length === 1 ? "" : "s"} ready`
                  : "No supported files"
              }
              subtitle={skipped ? `${skipped} unsupported will be skipped` : undefined}
              trailing={
                <Button variant="ghost" size="sm" onClick={() => setFiles([])} disabled={busy}>
                  Clear all
                </Button>
              }
            />
            <CardBody className="pt-2 space-y-1.5">
              <ul className="max-h-72 overflow-y-auto rounded-md border border-border bg-canvas">
                {files.map((f, i) => {
                  const ok = isSupported(f.name);
                  const icon = iconFor(f.name, f.type);
                  const Icon = icon.Icon;
                  return (
                    <li
                      key={`${f.name}-${i}`}
                      className={clsx(
                        "flex items-center gap-3 border-b border-border px-3 py-2 last:border-b-0",
                        !ok && "opacity-60"
                      )}
                    >
                      <span className={clsx("grid h-8 w-8 shrink-0 place-items-center rounded-md", icon.bg)}>
                        <Icon className={clsx("h-3.5 w-3.5", icon.fg)} />
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-[12.5px] font-medium text-ink-1" title={f.name}>
                          {f.name}
                        </span>
                        <span className="block text-[10px] tabular-nums text-ink-3">
                          {prettySize(f.size)}
                          {!ok ? " · unsupported, will be skipped" : ""}
                        </span>
                      </span>
                      <button
                        onClick={() => removeFile(i)}
                        disabled={busy}
                        className="focus-ring text-ink-3 hover:text-rose-600 disabled:opacity-50"
                        title="Remove from list"
                      >
                        <X className="h-3.5 w-3.5" />
                      </button>
                    </li>
                  );
                })}
              </ul>

              {eligible.length === 0 && (
                <div className="mt-2 flex items-start gap-2 rounded-md border border-amber-200 bg-amber-50 px-3 py-2.5 text-[11px] text-amber-800 dark:border-amber-900/50 dark:bg-amber-950/40 dark:text-amber-300">
                  <AlertCircle className="mt-px h-3.5 w-3.5 shrink-0" />
                  None of the dropped files have a supported extension.
                </div>
              )}
            </CardBody>
          </Card>
        )}

        {activeJobId && (
          <section className="space-y-2">
            <div className="text-[10px] uppercase tracking-wider text-ink-3">
              Progress
            </div>
            <JobProgress jobId={activeJobId} />
          </section>
        )}
      </div>
    </div>
  );
}
