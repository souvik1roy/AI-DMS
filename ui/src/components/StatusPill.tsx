import clsx from "clsx";

import type { JobStatus } from "@/lib/api";

const STYLES: Record<JobStatus, { label: string; cls: string; dot: string }> = {
  pending:   { label: "Queued",    cls: "bg-sunken text-ink-2",                                 dot: "bg-ink-3" },
  fetching:  { label: "Uploading", cls: "bg-accent-soft text-accent-ink",                        dot: "bg-accent" },
  parsing:   { label: "Reading",   cls: "bg-accent-soft text-accent-ink",                        dot: "bg-accent" },
  organizing:{ label: "Planning",  cls: "bg-accent-soft text-accent-ink",                        dot: "bg-accent" },
  filing:    { label: "Filing",    cls: "bg-accent-soft text-accent-ink",                        dot: "bg-accent" },
  done:      { label: "Done",      cls: "bg-accent text-white",                                  dot: "bg-white/80" },
  partial:   { label: "Partial",   cls: "bg-amber-50 text-amber-800 dark:bg-amber-950/40 dark:text-amber-300", dot: "bg-amber-500" },
  failed:    { label: "Failed",    cls: "bg-rose-50 text-rose-700 dark:bg-rose-950/40 dark:text-rose-300",     dot: "bg-rose-500" },
  cancelled: { label: "Cancelled", cls: "bg-sunken text-ink-3",                                  dot: "bg-ink-3" },
};

interface Props {
  status: JobStatus;
  className?: string;
}

export function StatusPill({ status, className }: Props) {
  const s = STYLES[status] || STYLES.pending;
  return (
    <span
      className={clsx(
        "inline-flex items-center gap-1.5 rounded-chip px-2 py-0.5 text-[11px] font-medium",
        s.cls,
        className
      )}
    >
      <span className={clsx("h-1.5 w-1.5 rounded-full", s.dot)} />
      {s.label}
    </span>
  );
}
