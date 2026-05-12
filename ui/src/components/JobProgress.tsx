import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { Check, Loader2, Square, XCircle } from "lucide-react";
import clsx from "clsx";

import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { StatusPill } from "@/components/StatusPill";
import { cancelJob, getJob, type Job, type JobStatus } from "@/lib/api";

const STEP_ORDER: JobStatus[] = ["fetching", "parsing", "filing", "done"];
const STEP_LABEL: Record<JobStatus, string> = {
  pending: "Queued",
  fetching: "Uploading",
  parsing: "Reading",
  organizing: "Planning", // legacy — pre-migration rows only
  filing: "Filing",
  done: "Done",
  partial: "Partial",
  failed: "Failed",
  cancelled: "Cancelled",
};

export function JobProgress({ jobId }: { jobId: string }) {
  const queryClient = useQueryClient();
  const { data, isError, error } = useQuery({
    queryKey: ["job", jobId],
    queryFn: () => getJob(jobId),
    refetchInterval: (q) => {
      const s = q.state.data?.status;
      if (!s) return 800;
      if (s === "done" || s === "failed" || s === "partial" || s === "cancelled") return false;
      return 800;
    },
  });
  const cancel = useMutation({
    mutationFn: () => cancelJob(jobId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["job", jobId] });
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
    },
  });

  if (isError) {
    return (
      <Card className="px-4 py-3 text-sm text-rose-700 dark:text-rose-300" variant="flat">
        Could not read job state: {(error as Error).message}
      </Card>
    );
  }
  if (!data) {
    return (
      <Card variant="flat" className="flex items-center gap-2 px-4 py-3 text-sm text-ink-3">
        <Loader2 className="h-4 w-4 animate-spin" />
        Starting job…
      </Card>
    );
  }

  const terminal =
    data.status === "done" ||
    data.status === "partial" ||
    data.status === "failed" ||
    data.status === "cancelled";
  const failed = data.status === "failed" || data.status === "cancelled";
  const stats = (data.stats || {}) as Job["stats"] & { skipped?: number };
  const filed = stats?.filed ?? 0;
  const parsed = stats?.parsed ?? 0;
  const fetched = stats?.fetched ?? 0;
  const skipped = stats?.skipped ?? 0;
  const errs = stats?.errors ?? 0;
  const allSkipped = terminal && !failed && fetched === 0 && skipped > 0;

  const reached = STEP_ORDER.indexOf(data.status as JobStatus);

  return (
    <Card className="overflow-hidden">
      <div className="flex items-center justify-between px-5 py-3">
        <div className="flex items-center gap-2.5">
          {failed ? (
            <XCircle className="h-4 w-4 text-rose-500" />
          ) : terminal ? (
            <Check className="h-4 w-4 text-accent" />
          ) : (
            <Loader2 className="h-4 w-4 animate-spin text-accent" />
          )}
          <span className="text-sm font-medium text-ink-1">
            {STEP_LABEL[data.status as JobStatus]}
          </span>
          <StatusPill status={data.status as JobStatus} className="ml-1.5" />
        </div>
        <div className="flex items-center gap-3">
          <div className="text-xs tabular-nums text-ink-3">
            {filed} filed · {parsed} parsed · {fetched} new
            {skipped ? ` · ${skipped} already filed` : ""}
            {errs ? ` · ${errs} errors` : ""}
          </div>
          {!terminal && (
            <Button
              variant="secondary"
              size="sm"
              onClick={() => cancel.mutate()}
              loading={cancel.isPending}
              leftIcon={!cancel.isPending ? <Square className="h-3 w-3" /> : undefined}
            >
              Stop
            </Button>
          )}
        </div>
      </div>

      <div className="border-t border-border bg-canvas px-5 py-5">
        <Stepper currentIndex={reached} terminal={terminal} failed={failed} />
      </div>

      {allSkipped && (
        <div className="border-t border-amber-200 bg-amber-50 px-5 py-3 text-xs text-amber-800 dark:border-amber-900/50 dark:bg-amber-950/40 dark:text-amber-300">
          All {skipped} document{skipped === 1 ? "" : "s"} were already filed in a previous run.
          The organised tree has not changed.
        </div>
      )}

      {data.error_message && (
        <div className="border-t border-rose-200 bg-rose-50 px-5 py-3 text-xs text-rose-700 dark:border-rose-950/50 dark:bg-rose-950/40 dark:text-rose-300">
          {data.error_message}
        </div>
      )}
    </Card>
  );
}

function Stepper({
  currentIndex,
  terminal,
  failed,
}: {
  currentIndex: number;
  terminal: boolean;
  failed: boolean;
}) {
  return (
    <ol className="flex items-center gap-0">
      {STEP_ORDER.map((s, i) => {
        const passed = currentIndex > i || (terminal && !failed);
        const here = currentIndex === i && !terminal;
        return (
          <li key={s} className="flex items-center gap-2.5">
            <StepDot passed={passed} here={here} index={i} failed={failed && here} />
            <span
              className={clsx(
                "text-[11.5px]",
                passed ? "text-ink-1" : here ? "font-medium text-ink-1" : "text-ink-3"
              )}
            >
              {STEP_LABEL[s]}
            </span>
            {i < STEP_ORDER.length - 1 && (
              <span className="relative mx-2 block h-px w-10 bg-border">
                <motion.span
                  className="absolute inset-y-0 left-0 block bg-accent"
                  initial={{ width: 0 }}
                  animate={{ width: passed ? "100%" : 0 }}
                  transition={{ duration: 0.35, ease: "easeOut" }}
                />
              </span>
            )}
          </li>
        );
      })}
    </ol>
  );
}

function StepDot({
  passed,
  here,
  index,
  failed,
}: {
  passed: boolean;
  here: boolean;
  index: number;
  failed: boolean;
}) {
  if (passed) {
    return (
      <motion.span
        initial={{ scale: 0.7, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ type: "spring", stiffness: 360, damping: 22 }}
        className="grid h-5 w-5 place-items-center rounded-full bg-accent text-white"
      >
        <Check className="h-3 w-3" strokeWidth={3} />
      </motion.span>
    );
  }
  if (here) {
    return (
      <span className="relative grid h-5 w-5 place-items-center rounded-full bg-accent-soft text-accent-ink ring-2 ring-accent">
        <span className="text-[10px] font-semibold">{index + 1}</span>
        {!failed && (
          <motion.span
            aria-hidden
            className="absolute inset-0 rounded-full ring-2 ring-accent"
            animate={{ scale: [1, 1.35, 1], opacity: [0.6, 0, 0.6] }}
            transition={{ duration: 1.6, repeat: Infinity, ease: "easeOut" }}
          />
        )}
      </span>
    );
  }
  return (
    <span className="grid h-5 w-5 place-items-center rounded-full bg-surface text-ink-3 ring-1 ring-border">
      <span className="text-[10px] font-semibold">{index + 1}</span>
    </span>
  );
}
