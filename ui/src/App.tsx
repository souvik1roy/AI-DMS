import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import {
  ArrowUpRight,
  FilePlus,
  FolderTree,
  History,
  LayoutDashboard,
  Settings as SettingsIcon,
  type LucideIcon,
} from "lucide-react";
import clsx from "clsx";

import { Logo } from "./components/Logo";
import { StatusPill } from "./components/StatusPill";
import { Badge } from "./components/ui/Badge";
import { Browse } from "./routes/browse";
import { Dashboard } from "./routes/dashboard";
import { NewJob } from "./routes/new-job";
import { PastJobs } from "./routes/past-jobs";
import { Settings } from "./routes/settings";
import { getDashboardStats, listJobs, type JobRow, type JobStatus } from "./lib/api";
import { relativeTime } from "./lib/format";
import { useAppStore } from "./lib/store";

type Tab = "dashboard" | "browse" | "upload" | "past" | "settings";

interface NavItem {
  id: Tab;
  label: string;
  icon: LucideIcon;
}

const NAV: NavItem[] = [
  { id: "dashboard", label: "Dashboard", icon: LayoutDashboard },
  { id: "browse", label: "Browse", icon: FolderTree },
  { id: "upload", label: "Upload", icon: FilePlus },
  { id: "past", label: "Past jobs", icon: History },
  { id: "settings", label: "Settings", icon: SettingsIcon },
];

export default function App() {
  const [tab, setTab] = useState<Tab>("dashboard");

  return (
    <div className="flex min-h-full bg-canvas text-ink-1">
      <Sidebar tab={tab} setTab={setTab} />
      <main className="flex-1 overflow-y-auto">
        {tab === "dashboard" && (
          <Dashboard
            onJumpType={(type) => {
              setTab("browse");
              useAppStore.getState().setBrowseTypeFilter(type);
            }}
            onJumpUpload={() => setTab("upload")}
            onJumpPast={() => setTab("past")}
          />
        )}
        {tab === "browse" && <Browse />}
        {tab === "upload" && <NewJob />}
        {tab === "past" && <PastJobs onNewJob={() => setTab("upload")} />}
        {tab === "settings" && <Settings />}
      </main>
    </div>
  );
}

function Sidebar({ tab, setTab }: { tab: Tab; setTab: (t: Tab) => void }) {
  const activeJobId = useAppStore((s) => s.activeJobId);
  const jobs = useQuery({
    queryKey: ["jobs"],
    queryFn: listJobs,
    refetchInterval: activeJobId ? 1500 : 15000,
  });
  const stats = useQuery({
    queryKey: ["dashboard", "stats"],
    queryFn: getDashboardStats,
    staleTime: 30_000,
    refetchInterval: 30_000,
  });
  const lastJob = jobs.data?.[0];
  const totalDocs = stats.data?.total_documents ?? 0;

  return (
    <aside className="flex w-[248px] shrink-0 flex-col border-r border-border bg-surface">
      <div className="px-4 pt-5 pb-4">
        <Logo size="md" withWordmark />
      </div>

      <nav className="relative flex flex-col gap-0.5 px-2 pb-3">
        {NAV.map(({ id, label, icon: Icon }) => {
          const active = tab === id;
          const showBadge = id === "browse" && totalDocs > 0;
          return (
            <button
              key={id}
              onClick={() => setTab(id)}
              className={clsx(
                "focus-ring group relative flex items-center gap-2.5 rounded-md px-2.5 py-1.5 text-left text-[13px] transition-colors",
                active ? "text-ink-1" : "text-ink-2 hover:text-ink-1"
              )}
            >
              {active && (
                <motion.span
                  layoutId="sidebar-pill"
                  transition={{ type: "spring", stiffness: 380, damping: 32 }}
                  className="absolute inset-0 -z-0 rounded-md bg-accent-soft"
                />
              )}
              <span className="relative z-10 flex flex-1 items-center gap-2.5">
                <Icon
                  className={clsx(
                    "h-4 w-4 transition-colors",
                    active
                      ? "text-accent-ink"
                      : "text-ink-3 group-hover:text-ink-1"
                  )}
                />
                {label}
                {showBadge && (
                  <Badge tone="neutral" size="sm" className="ml-auto">
                    {totalDocs}
                  </Badge>
                )}
              </span>
            </button>
          );
        })}
      </nav>

      {lastJob && (
        <LastRunCard job={lastJob} onView={() => setTab("past")} />
      )}

      <div className="mt-auto flex items-center justify-end gap-2 border-t border-border px-4 py-3">
        <div className="text-[10px] text-ink-3">v0.3.0 · web</div>
      </div>
    </aside>
  );
}

function LastRunCard({ job, onView }: { job: JobRow; onView: () => void }) {
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

  return (
    <div className="mx-3 mt-3 rounded-card border border-border bg-canvas p-3 text-xs">
      <div className="mb-2 flex items-center justify-between">
        <span className="text-[10px] uppercase tracking-wider text-ink-3">
          Last run
        </span>
        <StatusPill status={job.status as JobStatus} />
      </div>
      <div className="font-display text-[14px] font-semibold text-ink-1 tabular-nums">
        {stats.filed ?? 0} filed
      </div>
      <div className="text-[11px] text-ink-3">
        {stats.skipped ? `${stats.skipped} skipped · ` : ""}
        {stats.errors ? `${stats.errors} errors · ` : ""}
        {relativeTime(job.started_at)}
      </div>
      <button
        onClick={onView}
        className="focus-ring mt-2.5 inline-flex items-center gap-1 text-[11px] font-medium text-accent-ink hover:underline"
      >
        View history <ArrowUpRight className="h-3 w-3" />
      </button>
    </div>
  );
}
