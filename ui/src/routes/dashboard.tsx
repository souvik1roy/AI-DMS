import { useQuery } from "@tanstack/react-query";
import {
  ArrowRight,
  Building2,
  FileText,
  FolderTree,
  Layers,
  Sparkles,
  TrendingUp,
  Upload,
} from "lucide-react";
import clsx from "clsx";

import { Badge } from "@/components/ui/Badge";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Skeleton } from "@/components/ui/Skeleton";
import { Stat } from "@/components/ui/Stat";
import { Topbar } from "@/components/Topbar";
import { Button } from "@/components/ui/Button";
import {
  getDashboardStats,
  openDocument,
  type DashboardStats,
} from "@/lib/api";
import { iconFor } from "@/lib/file-icon";
import { prettyFolderName, relativeTime, typeChipColor } from "@/lib/format";

interface Props {
  onJumpType: (type: string) => void;
  onJumpUpload: () => void;
  onJumpPast: () => void;
}

export function Dashboard({ onJumpType, onJumpUpload, onJumpPast }: Props) {
  const q = useQuery({
    queryKey: ["dashboard", "stats"],
    queryFn: getDashboardStats,
    staleTime: 30_000,
  });
  const s = q.data;

  return (
    <div className="flex flex-col">
      <Topbar
        title="Dashboard"
        subtitle="At-a-glance view of your AI-DMS library"
        trailing={
          <Button variant="primary" size="sm" leftIcon={<Upload className="h-3.5 w-3.5" />} onClick={onJumpUpload}>
            Upload
          </Button>
        }
      />

      <div className="mx-auto w-full max-w-6xl space-y-6 px-6 py-6">
        {/* Hero stats row */}
        <section className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          {q.isLoading || !s ? (
            <>
              <Skeleton className="h-[112px]" />
              <Skeleton className="h-[112px]" />
              <Skeleton className="h-[112px]" />
              <Skeleton className="h-[112px]" />
            </>
          ) : (
            <>
              <Stat
                label="Total documents"
                value={fmt(s.total_documents)}
                icon={FileText}
                hint="Filed across all types"
              />
              <Stat
                label="Filed this week"
                value={fmt(s.filed_this_week)}
                icon={TrendingUp}
                trend={weekTrend(s)}
                hint="vs previous 7 days"
              />
              <Stat
                label="Document types"
                value={fmt(s.types_used)}
                icon={Layers}
                hint="in active use"
              />
              <Stat
                label="Entities tracked"
                value={fmt(s.entities_used)}
                icon={Building2}
                hint="across all documents"
              />
            </>
          )}
        </section>

        {/* Two-column: top types + top entities */}
        <section className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <Card>
            <CardHeader
              title="Top document types"
              subtitle="By number of filed documents"
              trailing={
                <Badge tone="accent" size="sm">
                  Live
                </Badge>
              }
            />
            <CardBody className="pt-3">
              {q.isLoading || !s ? (
                <BarListSkeleton />
              ) : (
                <BarList
                  items={s.top_types.map((t) => ({
                    key: t.type,
                    label: t.type,
                    value: t.count,
                    onClick: () => onJumpType(t.type),
                  }))}
                />
              )}
            </CardBody>
          </Card>

          <Card>
            <CardHeader
              title="Top entities"
              subtitle="Who owns the most filed documents"
            />
            <CardBody className="pt-3">
              {q.isLoading || !s ? (
                <BarListSkeleton />
              ) : (
                <BarList
                  items={s.top_entities.map((t) => ({
                    key: t.entity,
                    label: prettyFolderName(t.entity),
                    value: t.count,
                  }))}
                />
              )}
            </CardBody>
          </Card>
        </section>

        {/* Modality breakdown + recent uploads */}
        <section className="grid grid-cols-1 gap-4 lg:grid-cols-3">
          <Card className="lg:col-span-1">
            <CardHeader title="Modalities" subtitle="What we've ingested" />
            <CardBody className="pt-2 space-y-2">
              {q.isLoading || !s ? (
                <BarListSkeleton rows={3} />
              ) : s.modality_breakdown.length === 0 ? (
                <div className="rounded-md border border-dashed border-border bg-canvas px-3 py-6 text-center text-[12px] text-ink-3">
                  Nothing ingested yet.
                </div>
              ) : (
                <BarList
                  items={s.modality_breakdown.map((m) => ({
                    key: m.modality,
                    label: m.modality === "image" ? "Visual (PDF / image / Office)" : "Text (CSV / audio / video)",
                    value: m.count,
                  }))}
                />
              )}
            </CardBody>
          </Card>

          <Card className="lg:col-span-2">
            <CardHeader
              title="Recent uploads"
              subtitle="Last 10 filed documents"
              trailing={
                <Button variant="ghost" size="sm" onClick={onJumpPast}>
                  View all jobs <ArrowRight className="h-3 w-3" />
                </Button>
              }
            />
            <CardBody className="pt-1 px-0">
              {q.isLoading || !s ? (
                <div className="space-y-1 px-5 pb-3">
                  <Skeleton className="h-12" />
                  <Skeleton className="h-12" />
                  <Skeleton className="h-12" />
                </div>
              ) : s.recent_uploads.length === 0 ? (
                <EmptyHero onUpload={onJumpUpload} />
              ) : (
                <ul>
                  {s.recent_uploads.map((d) => (
                    <RecentRow key={d.id} doc={d} />
                  ))}
                </ul>
              )}
            </CardBody>
          </Card>
        </section>
      </div>
    </div>
  );
}

function BarList({
  items,
}: {
  items: { key: string; label: string; value: number; onClick?: () => void }[];
}) {
  if (items.length === 0) {
    return (
      <div className="rounded-md border border-dashed border-border bg-canvas px-3 py-6 text-center text-[12px] text-ink-3">
        Nothing here yet.
      </div>
    );
  }
  const max = Math.max(...items.map((i) => i.value), 1);
  return (
    <ul className="space-y-2">
      {items.map((it) => {
        const pct = (it.value / max) * 100;
        const RowEl = it.onClick ? "button" : "div";
        return (
          <li key={it.key}>
            <RowEl
              {...(it.onClick ? { onClick: it.onClick } : {})}
              className={clsx(
                "group flex w-full items-center gap-3 rounded-md px-1 py-1 text-left",
                it.onClick && "focus-ring hover:bg-sunken"
              )}
            >
              <span
                className={clsx(
                  "h-2 flex-1 rounded-chip bg-sunken",
                  it.onClick && "group-hover:bg-canvas"
                )}
              >
                <span
                  className="block h-full rounded-chip bg-accent transition-all duration-500 ease-spring"
                  style={{ width: `${pct}%` }}
                />
              </span>
              <span
                className="min-w-0 max-w-[40%] flex-shrink-0 truncate text-right text-[12px] text-ink-2"
                title={it.label}
              >
                {it.label}
              </span>
              <span className="w-8 shrink-0 text-right font-mono text-[12px] font-semibold text-ink-1 tabular-nums">
                {it.value}
              </span>
            </RowEl>
          </li>
        );
      })}
    </ul>
  );
}

function BarListSkeleton({ rows = 6 }: { rows?: number }) {
  return (
    <ul className="space-y-2">
      {Array.from({ length: rows }).map((_, i) => (
        <li key={i} className="flex items-center gap-3">
          <Skeleton className="h-2 flex-1" />
          <Skeleton className="h-3 w-16" />
          <Skeleton className="h-3 w-6" />
        </li>
      ))}
    </ul>
  );
}

function RecentRow({ doc }: { doc: DashboardStats["recent_uploads"][number] }) {
  const md = parseMd(doc.parsed_metadata_json);
  const icon = iconFor(doc.original_name);
  const Icon = icon.Icon;
  return (
    <li>
      <button
        onClick={() => openDocument(doc.id)}
        className="focus-ring flex w-full items-center gap-3 border-t border-border px-5 py-2.5 text-left transition-colors hover:bg-sunken first:border-t-0"
      >
        <span
          className={clsx(
            "grid h-9 w-9 shrink-0 place-items-center rounded-md",
            icon.bg
          )}
        >
          <Icon className={clsx("h-4 w-4", icon.fg)} />
        </span>
        <span className="min-w-0 flex-1">
          <span
            className="block truncate text-[13px] font-medium text-ink-1"
            title={doc.original_name}
          >
            {doc.original_name}
          </span>
          <span className="block truncate text-[11px] text-ink-3">
            {md.entity_name || "—"}
            {md.date ? ` · ${md.date}` : ""}
            {doc.filed_at ? ` · ${relativeTime(doc.filed_at)}` : ""}
          </span>
        </span>
        {md.document_type && (
          <span
            className={clsx(
              "shrink-0 rounded-chip px-2 py-0.5 text-[10px] font-medium",
              typeChipColor(md.document_type)
            )}
          >
            {md.document_type}
          </span>
        )}
      </button>
    </li>
  );
}

function EmptyHero({ onUpload }: { onUpload: () => void }) {
  return (
    <div className="flex flex-col items-center gap-3 px-6 py-10 text-center">
      <div className="grid h-12 w-12 place-items-center rounded-full bg-accent-soft text-accent-ink">
        <Sparkles className="h-5 w-5" />
      </div>
      <div>
        <div className="font-display text-sm font-semibold text-ink-1">
          No documents filed yet
        </div>
        <div className="mt-1 text-[12px] text-ink-3">
          Drop some PDFs, scans, spreadsheets or audio in to get started.
        </div>
      </div>
      <Button variant="primary" size="md" leftIcon={<Upload className="h-3.5 w-3.5" />} onClick={onUpload}>
        Upload your first batch
      </Button>
    </div>
  );
}

function parseMd(raw: string | null): Record<string, string> {
  if (!raw) return {};
  try {
    return JSON.parse(raw) as Record<string, string>;
  } catch {
    return {};
  }
}

function weekTrend(s: DashboardStats): { delta: number; suffix?: string } | null {
  if (s.filed_prev_week === 0 && s.filed_this_week === 0) return { delta: 0 };
  if (s.filed_prev_week === 0) return { delta: s.filed_this_week, suffix: "" };
  const delta = s.filed_this_week - s.filed_prev_week;
  return { delta };
}

function fmt(n: number): string {
  if (n >= 1000) return `${(n / 1000).toFixed(1)}k`;
  return String(n);
}

// Make FolderTree usable below without an import bloating the top:
void FolderTree;
