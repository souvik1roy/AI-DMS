import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AnimatePresence, motion } from "framer-motion";
import { toast } from "sonner";
import {
  ChevronDown,
  ChevronRight,
  ExternalLink,
  FileSearch,
  History,
  Loader2,
  Trash2,
} from "lucide-react";
import clsx from "clsx";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Skeleton } from "@/components/ui/Skeleton";
import { StatusPill } from "@/components/StatusPill";
import { Topbar } from "@/components/Topbar";
import { iconFor } from "@/lib/file-icon";
import { relativeTime, typeChipColor } from "@/lib/format";
import {
  deleteJob,
  getJobLog,
  listJobDocuments,
  listJobs,
  openDocument,
  type DocumentRow,
  type JobRow,
  type JobStatus,
  type ParseLogRecord,
} from "@/lib/api";

interface Props {
  onNewJob: () => void;
}

export function PastJobs({ onNewJob }: Props) {
  const jobs = useQuery({
    queryKey: ["jobs"],
    queryFn: listJobs,
    refetchInterval: 4000,
  });
  const [expanded, setExpanded] = useState<string | null>(null);

  return (
    <div className="flex flex-col">
      <Topbar
        title="Past jobs"
        subtitle="Every upload, scheduled run and source pull"
        trailing={
          <Button variant="primary" size="sm" onClick={onNewJob}>
            + Upload
          </Button>
        }
      />

      <div className="mx-auto w-full max-w-4xl space-y-3 px-6 py-6">
        {jobs.isLoading ? (
          <div className="space-y-2">
            <Skeleton className="h-16" />
            <Skeleton className="h-16" />
            <Skeleton className="h-16" />
          </div>
        ) : !jobs.data || jobs.data.length === 0 ? (
          <Card className="flex flex-col items-center px-6 py-14 text-center" variant="flat">
            <div className="grid h-11 w-11 place-items-center rounded-full bg-accent-soft text-accent-ink">
              <History className="h-5 w-5" />
            </div>
            <div className="mt-3 font-display text-sm font-semibold text-ink-1">
              No jobs yet
            </div>
            <div className="mt-1 text-[12px] text-ink-3">
              Drop a batch of documents to see it appear here.
            </div>
            <Button variant="primary" size="sm" className="mt-4" onClick={onNewJob}>
              Start a new job
            </Button>
          </Card>
        ) : (
          jobs.data.map((j) => (
            <JobCard
              key={j.id}
              job={j}
              expanded={expanded === j.id}
              onToggle={() => setExpanded(expanded === j.id ? null : j.id)}
            />
          ))
        )}
      </div>
    </div>
  );
}

function JobCard({
  job,
  expanded,
  onToggle,
}: {
  job: JobRow;
  expanded: boolean;
  onToggle: () => void;
}) {
  const queryClient = useQueryClient();
  let stats: {
    fetched?: number;
    parsed?: number;
    filed?: number;
    skipped?: number;
    errors?: number;
  } = {};
  try {
    if (job.stats_json) stats = JSON.parse(job.stats_json);
  } catch {
    stats = {};
  }
  const terminal = ["done", "failed", "partial", "cancelled"].includes(job.status);
  const remove = useMutation({
    mutationFn: () => deleteJob(job.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard", "stats"] });
      toast.success("Job deleted");
    },
    onError: (e) => toast.error("Could not delete job", { description: String(e) }),
  });

  return (
    <Card className="overflow-hidden">
      <button
        onClick={onToggle}
        className="focus-ring flex w-full items-center gap-3 px-5 py-4 text-left hover:bg-sunken"
      >
        <span className="grid h-7 w-7 place-items-center rounded-md bg-sunken text-ink-3">
          {expanded ? (
            <ChevronDown className="h-3.5 w-3.5" />
          ) : (
            <ChevronRight className="h-3.5 w-3.5" />
          )}
        </span>
        <span className="min-w-0 flex-1">
          <span className="block text-[13.5px] font-semibold text-ink-1">
            {new Date(job.started_at).toLocaleString(undefined, {
              month: "short",
              day: "numeric",
              hour: "2-digit",
              minute: "2-digit",
            })}
          </span>
          <span className="block font-mono text-[10px] text-ink-3">
            {job.id.slice(-12)} · {job.trigger}
          </span>
        </span>
        <StatusPill status={job.status as JobStatus} />
        <span className="hidden text-right text-[12px] tabular-nums text-ink-2 md:block">
          {stats.filed ?? 0} filed
          {stats.skipped ? ` · ${stats.skipped} skipped` : ""}
          {stats.errors ? ` · ${stats.errors} err` : ""}
        </span>
        {terminal && (
          <button
            onClick={(e) => {
              e.stopPropagation();
              if (
                confirm(
                  `Delete job ${job.id.slice(-12)} and ${stats.filed ?? 0} filed file(s)?`
                )
              ) {
                remove.mutate();
              }
            }}
            disabled={remove.isPending}
            className="focus-ring grid h-7 w-7 place-items-center rounded-md text-ink-3 hover:bg-rose-50 hover:text-rose-600 disabled:opacity-50 dark:hover:bg-rose-950/40"
            title="Delete job and its files"
          >
            {remove.isPending ? (
              <Loader2 className="h-3 w-3 animate-spin" />
            ) : (
              <Trash2 className="h-3 w-3" />
            )}
          </button>
        )}
      </button>

      <AnimatePresence initial={false}>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.18, ease: "easeOut" }}
            style={{ overflow: "hidden" }}
            className="border-t border-border bg-canvas"
          >
            <div className="space-y-3 px-5 py-4 text-[12px] text-ink-2">
              {job.destination_folder && (
                <div className="flex items-center gap-2 text-[11px] text-ink-2">
                  <span className="text-ink-3">Destination:</span>
                  <span className="truncate font-mono text-accent-ink" title={job.destination_folder}>
                    organized/{job.destination_folder}/…
                  </span>
                </div>
              )}
              <JobDocuments jobId={job.id} />
              <JobParseLog jobId={job.id} />
              {job.error_message && (
                <div className="rounded-md border border-rose-200 bg-rose-50 px-2.5 py-2 text-[11px] text-rose-700 dark:border-rose-950/50 dark:bg-rose-950/40 dark:text-rose-300">
                  <span className="font-medium">Error: </span>
                  {job.error_message}
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </Card>
  );
}

function JobParseLog({ jobId }: { jobId: string }) {
  const [show, setShow] = useState(false);
  const q = useQuery({
    queryKey: ["job-log", jobId],
    queryFn: () => getJobLog(jobId),
    enabled: show,
    retry: false,
  });
  if (!show) {
    return (
      <Button variant="secondary" size="sm" onClick={() => setShow(true)} leftIcon={<FileSearch className="h-3 w-3" />}>
        Show parse log
      </Button>
    );
  }
  if (q.isLoading) {
    return (
      <div className="flex items-center gap-2 text-[11px] text-ink-3">
        <Loader2 className="h-3 w-3 animate-spin" /> Loading parse log…
      </div>
    );
  }
  if (q.error) {
    return (
      <div className="rounded-md border border-amber-200 bg-amber-50 px-2.5 py-2 text-[11px] text-amber-800 dark:border-amber-900/50 dark:bg-amber-950/40 dark:text-amber-300">
        No archived parse log for this job.
      </div>
    );
  }
  const records: ParseLogRecord[] = q.data ?? [];
  if (records.length === 0)
    return <div className="text-[11px] text-ink-3">Archived log is empty.</div>;
  return (
    <div className="space-y-1.5">
      <div className="text-[10px] uppercase tracking-wider text-ink-3">
        Parse log · {records.length} record{records.length === 1 ? "" : "s"}
      </div>
      <ul className="space-y-1">
        {records.map((r, i) => (
          <li
            key={(r.doc_id as string) ?? i}
            className="rounded-md border border-border bg-surface px-2.5 py-1.5 text-[11px] text-ink-2"
          >
            <div className="truncate text-ink-1" title={r.original_name as string}>
              {(r.original_name as string) ?? "(unnamed)"}
            </div>
            <div className="mt-0.5 text-ink-3">
              {r.document_type || "Uncategorized"}
              {r.entity_name ? ` · ${r.entity_name}` : ""}
              {r.date ? ` · ${r.date}` : ""}
              {typeof r.confidence === "number" ? ` · conf ${r.confidence.toFixed(2)}` : ""}
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

function JobDocuments({ jobId }: { jobId: string }) {
  const docs = useQuery({
    queryKey: ["job-docs", jobId],
    queryFn: () => listJobDocuments(jobId),
  });
  if (docs.isLoading)
    return (
      <div className="flex items-center gap-2 text-xs text-ink-3">
        <Loader2 className="h-3 w-3 animate-spin" /> Loading documents…
      </div>
    );
  if (!docs.data || docs.data.length === 0)
    return <div className="text-xs text-ink-3">No documents recorded for this job.</div>;
  return (
    <ul className="space-y-1.5">
      {docs.data.map((d) => (
        <DocRow key={d.id} doc={d} />
      ))}
    </ul>
  );
}

function DocRow({ doc }: { doc: DocumentRow }) {
  const md = (() => {
    try {
      return doc.parsed_metadata_json ? JSON.parse(doc.parsed_metadata_json) : null;
    } catch {
      return null;
    }
  })();
  const icon = iconFor(doc.original_name);
  const Icon = icon.Icon;
  const statusTone =
    doc.status === "filed"
      ? "accent"
      : doc.status === "parsed"
      ? "indigo"
      : doc.status === "skipped_duplicate"
      ? "amber"
      : doc.status === "failed"
      ? "rose"
      : "neutral";
  return (
    <li className="flex items-start gap-3 rounded-md border border-border bg-surface px-2.5 py-2 text-[12px]">
      <span className={clsx("grid h-7 w-7 shrink-0 place-items-center rounded-md", icon.bg)}>
        <Icon className={clsx("h-3.5 w-3.5", icon.fg)} />
      </span>
      <div className="min-w-0 flex-1">
        <div className="truncate text-ink-1" title={doc.original_name}>
          {doc.original_name}
        </div>
        {md && md.document_type && (
          <div className="mt-0.5 flex flex-wrap items-center gap-1.5">
            <span
              className={clsx(
                "rounded-chip px-1.5 py-0.5 text-[10px] font-medium",
                typeChipColor(md.document_type)
              )}
            >
              {md.document_type}
            </span>
            {md.entity_name && <span className="text-[11px] text-ink-3">· {md.entity_name}</span>}
            {md.date && <span className="text-[11px] text-ink-3">· {md.date}</span>}
          </div>
        )}
        {doc.error_message && (
          <div className="mt-0.5 text-[11px] text-rose-700 dark:text-rose-300">
            {doc.error_message}
          </div>
        )}
      </div>
      <Badge tone={statusTone} size="sm" className="shrink-0">
        {doc.status.replace("_", " ")}
      </Badge>
      {doc.final_path && (
        <button
          onClick={() => openDocument(doc.id)}
          className="focus-ring shrink-0 text-ink-3 hover:text-ink-1"
          title="Open in new tab"
        >
          <ExternalLink className="h-3.5 w-3.5" />
        </button>
      )}
    </li>
  );
}

// Keep these so the JSX above stays happy with TS strict.
void relativeTime;
