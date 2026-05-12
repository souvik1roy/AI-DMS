import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import {
  ChevronDown,
  ChevronRight,
  Database,
  ExternalLink,
  Folder,
  FolderOpen,
  Grid3x3,
  Headphones,
  Home,
  Layers,
  List,
  Loader2,
  RefreshCw,
  Search,
  SlidersHorizontal,
} from "lucide-react";
import clsx from "clsx";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Skeleton } from "@/components/ui/Skeleton";
import { Topbar } from "@/components/Topbar";
import {
  browse,
  openOrganizedKey,
  type BrowseEntry,
} from "@/lib/api";
import { iconFor } from "@/lib/file-icon";
import { prettyFolderName, prettySize, typeChipColor } from "@/lib/format";
import { useAppStore } from "@/lib/store";

type ViewMode = "grid" | "list";
type SortKey = "name" | "date" | "size" | "type";

export function Browse() {
  const [prefix, setPrefix] = useState<string>("");
  const [query, setQuery] = useState<string>("");
  const [view, setView] = useState<ViewMode>("grid");
  const [sort, setSort] = useState<SortKey>("name");
  const [typeFilter, setTypeFilter] = useState<string | null>(null);

  // Pre-applied filter pushed by Dashboard (cleared after first read).
  const pushedFilter = useAppStore((s) => s.browseTypeFilter);
  const clearPushedFilter = useAppStore((s) => s.setBrowseTypeFilter);
  useEffect(() => {
    if (pushedFilter) {
      setTypeFilter(pushedFilter);
      clearPushedFilter(null);
    }
  }, [pushedFilter, clearPushedFilter]);

  const q = useQuery({
    queryKey: ["browse", prefix],
    queryFn: () => browse(prefix),
    staleTime: 10_000,
  });

  const all = q.data?.entries ?? [];
  const folders = all.filter((e) => e.is_folder);
  const files = all.filter((e) => !e.is_folder);

  const typeCounts = useMemo(() => {
    const m = new Map<string, number>();
    for (const f of files) {
      const k = f.document_type || "Untagged";
      m.set(k, (m.get(k) ?? 0) + 1);
    }
    return [...m.entries()].sort((a, b) => b[1] - a[1]);
  }, [files]);

  const filteredFiles = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return files.filter((e) => {
      if (typeFilter && (e.document_type || "Untagged") !== typeFilter) return false;
      if (!needle) return true;
      const fields = [
        e.name,
        e.original_name,
        e.document_type,
        e.entity_name,
        e.person_name,
        e.date,
        e.version,
        e.status,
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();
      return fields.includes(needle);
    });
  }, [files, query, typeFilter]);

  const filteredFolders = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return folders;
    return folders.filter((f) =>
      prettyFolderName(f.name).toLowerCase().includes(needle)
    );
  }, [folders, query]);

  const sortedFiles = useMemo(() => {
    const arr = [...filteredFiles];
    arr.sort((a, b) => {
      switch (sort) {
        case "date":
          return (b.date || b.updated_at || "").localeCompare(
            a.date || a.updated_at || ""
          );
        case "size":
          return (b.size ?? 0) - (a.size ?? 0);
        case "type":
          return (a.document_type || "").localeCompare(b.document_type || "");
        case "name":
        default:
          return (a.original_name || a.name).localeCompare(
            b.original_name || b.name
          );
      }
    });
    return arr;
  }, [filteredFiles, sort]);

  const totalFiltered = filteredFolders.length + filteredFiles.length;
  const currentFolderLabel = prefix
    ? prettyFolderName(prefix.split("/").slice(-1)[0])
    : "All documents";

  return (
    <div className="flex">
      {/* Left rail: folder tree */}
      <aside className="sticky top-0 hidden h-screen w-[280px] shrink-0 flex-col border-r border-border bg-surface md:flex">
        <div className="flex items-center gap-2 border-b border-border px-4 py-3">
          <div className="grid h-7 w-7 place-items-center rounded-md bg-accent-soft text-accent-ink">
            <Database className="h-3.5 w-3.5" />
          </div>
          <div>
            <div className="text-[13px] font-semibold text-ink-1">AI-DMS</div>
            <div className="text-[10px] text-ink-3">Supabase bucket</div>
          </div>
        </div>
        <div className="flex-1 overflow-y-auto px-2 py-3">
          <FolderTreeRoot
            currentPrefix={prefix}
            onSelect={(p) => {
              setPrefix(p);
              setTypeFilter(null);
            }}
          />
        </div>
      </aside>

      {/* Main pane */}
      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar
          title="Document library"
          subtitle="Mirrors the AI-DMS bucket"
          trailing={
            <Button
              variant="ghost"
              size="sm"
              onClick={() => q.refetch()}
              leftIcon={
                <RefreshCw className={clsx("h-3 w-3", q.isFetching && "animate-spin")} />
              }
            >
              Refresh
            </Button>
          }
        />

        <div className="border-b border-border bg-surface px-6 py-5">
          <div className="flex items-end justify-between gap-4">
            <div className="min-w-0">
              <Breadcrumb prefix={prefix} onJump={setPrefix} />
              <h1
                className="mt-2 truncate font-display text-2xl font-semibold tracking-tight text-ink-1"
                title={prefix}
              >
                {currentFolderLabel}
              </h1>
              <div className="mt-1 text-[12px] text-ink-3">
                {folders.length} folder{folders.length === 1 ? "" : "s"}
                <span className="mx-1.5">·</span>
                {files.length} document{files.length === 1 ? "" : "s"}
                <span className="mx-1.5">·</span>
                {typeCounts.length} type{typeCounts.length === 1 ? "" : "s"}
              </div>
            </div>
            <div className="flex items-center gap-2">
              <SearchInput value={query} onChange={setQuery} />
              <SortMenu sort={sort} onChange={setSort} />
              <ViewToggle view={view} onChange={setView} />
            </div>
          </div>

          {typeCounts.length > 0 && (
            <div className="mt-4 flex flex-wrap items-center gap-1.5">
              <Chip active={typeFilter === null} onClick={() => setTypeFilter(null)}>
                All · {files.length}
              </Chip>
              {typeCounts.slice(0, 12).map(([type, count]) => (
                <Chip
                  key={type}
                  active={typeFilter === type}
                  onClick={() => setTypeFilter(typeFilter === type ? null : type)}
                >
                  {type} · {count}
                </Chip>
              ))}
              {typeCounts.length > 12 && (
                <span className="text-[10px] text-ink-3">
                  +{typeCounts.length - 12} more
                </span>
              )}
            </div>
          )}
        </div>

        <div className="flex-1 px-6 py-6">
          {q.isLoading ? (
            <GridSkeleton />
          ) : q.error ? (
            <Card className="px-4 py-3">
              <div className="text-sm text-rose-700">
                Could not list this folder: {(q.error as Error).message}
              </div>
            </Card>
          ) : all.length === 0 ? (
            <EmptyFolder isRoot={prefix === ""} />
          ) : (
            <div className="flex flex-col gap-7">
              {filteredFolders.length > 0 && (
                <section className="space-y-2.5">
                  <SectionHead label="Folders" count={filteredFolders.length} />
                  <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                    {filteredFolders.map((f) => (
                      <FolderCard
                        key={f.name}
                        entry={f}
                        parentPrefix={prefix}
                        onEnter={(p) => {
                          setPrefix(p);
                          setTypeFilter(null);
                        }}
                      />
                    ))}
                  </div>
                </section>
              )}

              {sortedFiles.length > 0 && (
                <section className="space-y-2.5">
                  <SectionHead
                    label="Documents"
                    count={sortedFiles.length}
                    suffix={
                      typeFilter || query
                        ? `(filtered from ${files.length})`
                        : undefined
                    }
                  />
                  {view === "grid" ? (
                    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                      {sortedFiles.map((file) => (
                        <DocumentCard
                          key={file.name}
                          entry={file}
                          parentPrefix={prefix}
                        />
                      ))}
                    </div>
                  ) : (
                    <DocumentTable rows={sortedFiles} parentPrefix={prefix} />
                  )}
                </section>
              )}

              {totalFiltered === 0 && (query || typeFilter) && (
                <Card className="px-6 py-10 text-center text-sm text-ink-3">
                  No matches in this folder.
                </Card>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/* ---------------- folder tree ---------------- */

function FolderTreeRoot({
  currentPrefix,
  onSelect,
}: {
  currentPrefix: string;
  onSelect: (path: string) => void;
}) {
  const q = useQuery({
    queryKey: ["browse", ""],
    queryFn: () => browse(""),
    staleTime: 10_000,
  });
  const folders = (q.data?.entries ?? []).filter((e) => e.is_folder);
  return (
    <ul className="space-y-0.5">
      <li>
        <button
          onClick={() => onSelect("")}
          className={clsx(
            "focus-ring flex w-full items-center gap-1.5 rounded-md px-2 py-1 text-left text-[12px]",
            currentPrefix === ""
              ? "bg-accent-soft text-accent-ink"
              : "text-ink-2 hover:bg-sunken hover:text-ink-1"
          )}
        >
          <Home className="h-3 w-3" />
          <span className="truncate">All documents</span>
        </button>
      </li>
      {q.isLoading &&
        Array.from({ length: 8 }).map((_, i) => (
          <li key={i} className="px-2 py-1">
            <Skeleton className="h-4 w-full" />
          </li>
        ))}
      {folders.map((f) => (
        <TreeNode
          key={f.name}
          name={f.name}
          path={f.name}
          depth={0}
          currentPrefix={currentPrefix}
          onSelect={onSelect}
        />
      ))}
    </ul>
  );
}

function TreeNode({
  name,
  path,
  depth,
  currentPrefix,
  onSelect,
}: {
  name: string;
  path: string;
  depth: number;
  currentPrefix: string;
  onSelect: (path: string) => void;
}) {
  const [open, setOpen] = useState(
    currentPrefix === path || currentPrefix.startsWith(path + "/")
  );
  const isActive = currentPrefix === path;
  const childrenQ = useQuery({
    queryKey: ["browse", path],
    queryFn: () => browse(path),
    staleTime: 10_000,
    enabled: open,
  });
  const subfolders = (childrenQ.data?.entries ?? []).filter((e) => e.is_folder);

  return (
    <li>
      <div
        className={clsx(
          "flex items-center gap-0.5 rounded-md",
          isActive && "bg-accent-soft"
        )}
        style={{ paddingLeft: depth * 10 }}
      >
        <button
          onClick={() => setOpen((v) => !v)}
          className="focus-ring grid h-5 w-5 place-items-center rounded text-ink-3 hover:bg-sunken hover:text-ink-1"
          title={open ? "Collapse" : "Expand"}
        >
          {open ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
        </button>
        <button
          onClick={() => onSelect(path)}
          className={clsx(
            "focus-ring flex min-w-0 flex-1 items-center gap-1.5 rounded-md px-1.5 py-1 text-left text-[12px]",
            isActive ? "text-accent-ink" : "text-ink-2 hover:bg-sunken hover:text-ink-1"
          )}
        >
          {open ? (
            <FolderOpen className="h-3 w-3 shrink-0 text-accent" />
          ) : (
            <Folder className="h-3 w-3 shrink-0 text-ink-3" />
          )}
          <span className="truncate">{prettyFolderName(name)}</span>
        </button>
      </div>
      {open && (
        <ul className="space-y-0.5">
          {childrenQ.isLoading && (
            <li
              className="py-0.5 text-[10px] text-ink-3"
              style={{ paddingLeft: (depth + 1) * 10 + 24 }}
            >
              <Loader2 className="inline h-3 w-3 animate-spin" />
            </li>
          )}
          {subfolders.map((sf) => (
            <TreeNode
              key={sf.name}
              name={sf.name}
              path={`${path}/${sf.name}`}
              depth={depth + 1}
              currentPrefix={currentPrefix}
              onSelect={onSelect}
            />
          ))}
        </ul>
      )}
    </li>
  );
}

/* ---------------- breadcrumb ---------------- */

function Breadcrumb({
  prefix,
  onJump,
}: {
  prefix: string;
  onJump: (p: string) => void;
}) {
  const crumbs = prefix
    ? prefix.split("/").filter(Boolean).map((label, i, all) => ({
        label,
        path: all.slice(0, i + 1).join("/"),
      }))
    : [];
  return (
    <nav className="flex min-w-0 flex-wrap items-center gap-1 text-[11px] text-ink-3">
      <button
        onClick={() => onJump("")}
        className={clsx(
          "focus-ring inline-flex items-center gap-1 rounded-md px-1.5 py-0.5",
          prefix === "" ? "text-accent-ink" : "hover:text-ink-1"
        )}
      >
        <Home className="h-3 w-3" />
        AI-DMS
      </button>
      {crumbs.map((c) => (
        <span key={c.path} className="flex items-center gap-1">
          <ChevronRight className="h-3 w-3" />
          <button
            onClick={() => onJump(c.path)}
            className="focus-ring max-w-[200px] truncate rounded-md px-1.5 py-0.5 hover:text-ink-1"
            title={c.path}
          >
            {prettyFolderName(c.label)}
          </button>
        </span>
      ))}
    </nav>
  );
}

/* ---------------- toolbar widgets ---------------- */

function SearchInput({
  value,
  onChange,
}: {
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <div className="relative">
      <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-ink-3" />
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder="Search this folder…"
        className="focus-ring h-9 w-64 rounded-md border border-border bg-surface py-1.5 pl-8 pr-3 text-[12px] text-ink-1 placeholder:text-ink-3"
      />
    </div>
  );
}

function SortMenu({
  sort,
  onChange,
}: {
  sort: SortKey;
  onChange: (s: SortKey) => void;
}) {
  const labels: Record<SortKey, string> = {
    name: "Name",
    date: "Date",
    size: "Size",
    type: "Type",
  };
  return (
    <div className="relative">
      <select
        value={sort}
        onChange={(e) => onChange(e.target.value as SortKey)}
        className="focus-ring h-9 appearance-none rounded-md border border-border bg-surface py-1.5 pl-8 pr-7 text-[12px] text-ink-1 hover:bg-sunken"
      >
        {(Object.keys(labels) as SortKey[]).map((k) => (
          <option key={k} value={k}>
            Sort: {labels[k]}
          </option>
        ))}
      </select>
      <SlidersHorizontal className="pointer-events-none absolute left-2.5 top-1/2 h-3 w-3 -translate-y-1/2 text-ink-3" />
    </div>
  );
}

function ViewToggle({
  view,
  onChange,
}: {
  view: ViewMode;
  onChange: (v: ViewMode) => void;
}) {
  return (
    <div className="inline-flex h-9 overflow-hidden rounded-md border border-border bg-surface">
      <button
        onClick={() => onChange("grid")}
        className={clsx(
          "focus-ring inline-flex items-center gap-1 px-2.5 text-[11px]",
          view === "grid"
            ? "bg-accent-soft text-accent-ink"
            : "text-ink-2 hover:bg-sunken hover:text-ink-1"
        )}
        title="Grid view"
      >
        <Grid3x3 className="h-3 w-3" />
      </button>
      <button
        onClick={() => onChange("list")}
        className={clsx(
          "focus-ring inline-flex items-center gap-1 px-2.5 text-[11px]",
          view === "list"
            ? "bg-accent-soft text-accent-ink"
            : "text-ink-2 hover:bg-sunken hover:text-ink-1"
        )}
        title="List view"
      >
        <List className="h-3 w-3" />
      </button>
    </div>
  );
}

/* ---------------- content components ---------------- */

function SectionHead({
  label,
  count,
  suffix,
}: {
  label: string;
  count: number;
  suffix?: string;
}) {
  return (
    <div className="flex items-baseline gap-2 text-[10px] uppercase tracking-wider text-ink-3">
      <span className="text-ink-2">{label}</span>
      <span className="text-ink-3">·</span>
      <span className="tabular-nums">{count}</span>
      {suffix && <span className="ml-1 normal-case text-ink-3">{suffix}</span>}
    </div>
  );
}

function FolderCard({
  entry,
  parentPrefix,
  onEnter,
}: {
  entry: BrowseEntry;
  parentPrefix: string;
  onEnter: (next: string) => void;
}) {
  const fullKey = parentPrefix ? `${parentPrefix}/${entry.name}` : entry.name;
  return (
    <motion.button
      onClick={() => onEnter(fullKey)}
      whileHover={{ y: -1 }}
      transition={{ duration: 0.15 }}
      className="focus-ring group flex w-full items-center gap-3 rounded-card border border-border bg-surface p-3.5 text-left shadow-elev-1 transition-all hover:border-accent/40 hover:shadow-elev-2"
    >
      <div className="grid h-10 w-10 shrink-0 place-items-center rounded-md bg-accent-soft text-accent-ink">
        <Folder className="h-4 w-4" />
      </div>
      <div className="min-w-0 flex-1">
        <div
          className="truncate text-[13px] font-semibold text-ink-1"
          title={prettyFolderName(entry.name)}
        >
          {prettyFolderName(entry.name)}
        </div>
        <div className="text-[10px] text-ink-3">Folder</div>
      </div>
      <ChevronRight className="h-3.5 w-3.5 shrink-0 text-ink-3 transition-transform group-hover:translate-x-0.5 group-hover:text-accent-ink" />
    </motion.button>
  );
}

function DocumentCard({
  entry,
  parentPrefix,
}: {
  entry: BrowseEntry;
  parentPrefix: string;
}) {
  const fullKey = parentPrefix ? `${parentPrefix}/${entry.name}` : entry.name;
  const display = entry.original_name || entry.name;
  const icon = iconFor(display, entry.content_type);
  const Icon = icon.Icon;
  return (
    <Card
      variant="interactive"
      onClick={() => openOrganizedKey(fullKey)}
      className="cursor-pointer p-3.5"
    >
      <div className="flex items-start gap-3">
        <div className={clsx("grid h-10 w-10 shrink-0 place-items-center rounded-md", icon.bg)}>
          <Icon className={clsx("h-4 w-4", icon.fg)} />
        </div>
        <div className="min-w-0 flex-1">
          <div
            className="line-clamp-2 break-words text-[12.5px] font-semibold text-ink-1"
            title={display}
          >
            {display}
          </div>
          {typeof entry.size === "number" && (
            <div className="mt-0.5 text-[10px] tabular-nums text-ink-3">
              {prettySize(entry.size)}
            </div>
          )}
        </div>
        <button
          onClick={(e) => {
            e.stopPropagation();
            openOrganizedKey(fullKey);
          }}
          className="focus-ring text-ink-3 transition-colors hover:text-ink-1"
          title="Open in new tab"
        >
          <ExternalLink className="h-3.5 w-3.5" />
        </button>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-1.5">
        {entry.document_type ? (
          <span
            className={clsx(
              "rounded-chip px-2 py-0.5 text-[10px] font-medium",
              typeChipColor(entry.document_type)
            )}
            title={entry.document_type}
          >
            {entry.document_type}
          </span>
        ) : (
          <Badge tone="neutral" size="sm">Untagged</Badge>
        )}
        {entry.version && <Badge tone="neutral" size="sm">v{entry.version}</Badge>}
      </div>

      <div className="mt-3 space-y-0.5 border-t border-border pt-2.5 text-[11px] text-ink-2">
        {entry.entity_name && <Field label="Entity" value={entry.entity_name} />}
        {entry.person_name && <Field label="Person" value={entry.person_name} />}
        {entry.date && <Field label="Date" value={entry.date} />}
        {!entry.entity_name && !entry.person_name && !entry.date && (
          <span className="text-ink-3">No metadata extracted</span>
        )}
        {entry.transcript_key && (
          <button
            onClick={(e) => {
              e.stopPropagation();
              openOrganizedKey(entry.transcript_key!);
            }}
            className="focus-ring mt-1 inline-flex items-center gap-1 rounded-chip bg-amber-50 px-2 py-0.5 text-[10px] font-medium text-amber-700 hover:bg-amber-100 dark:bg-amber-950/40 dark:text-amber-300 dark:hover:bg-amber-950/60"
            title="Open transcript"
          >
            <Headphones className="h-3 w-3" />
            Transcript
          </button>
        )}
      </div>
    </Card>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center gap-1.5">
      <span className="w-12 shrink-0 text-[10px] uppercase tracking-wider text-ink-3">
        {label}
      </span>
      <span className="truncate" title={value}>{value}</span>
    </div>
  );
}

function DocumentTable({
  rows,
  parentPrefix,
}: {
  rows: BrowseEntry[];
  parentPrefix: string;
}) {
  return (
    <Card className="overflow-hidden">
      <table className="w-full text-sm">
        <thead className="border-b border-border bg-canvas/60 text-[10px] uppercase tracking-wider text-ink-3">
          <tr>
            <th className="w-8 px-3 py-2" />
            <th className="px-3 py-2 text-left font-medium">Name</th>
            <th className="px-3 py-2 text-left font-medium">Document type</th>
            <th className="px-3 py-2 text-left font-medium">Entity</th>
            <th className="px-3 py-2 text-left font-medium">Date</th>
            <th className="px-3 py-2 text-right font-medium">Size</th>
            <th className="px-3 py-2" />
          </tr>
        </thead>
        <tbody>
          {rows.map((file) => {
            const fullKey = parentPrefix
              ? `${parentPrefix}/${file.name}`
              : file.name;
            const display = file.original_name || file.name;
            const icon = iconFor(display, file.content_type);
            const Icon = icon.Icon;
            return (
              <tr
                key={file.name}
                className="cursor-pointer border-b border-border last:border-b-0 hover:bg-sunken"
                onClick={() => openOrganizedKey(fullKey)}
              >
                <td className="px-3 py-2.5">
                  <Icon className={clsx("h-4 w-4", icon.fg)} />
                </td>
                <td className="px-3 py-2.5">
                  <div className="truncate text-[13px] text-ink-1" title={display}>
                    {display}
                  </div>
                  {file.person_name && (
                    <div className="truncate text-[11px] text-ink-3">
                      {file.person_name}
                    </div>
                  )}
                </td>
                <td className="px-3 py-2.5">
                  {file.document_type ? (
                    <span
                      className={clsx(
                        "rounded-chip px-2 py-0.5 text-[11px] font-medium",
                        typeChipColor(file.document_type)
                      )}
                    >
                      {file.document_type}
                    </span>
                  ) : (
                    <span className="text-[11px] text-ink-3">—</span>
                  )}
                </td>
                <td className="px-3 py-2.5 text-[12px] text-ink-2">
                  {file.entity_name || <span className="text-ink-3">Unknown</span>}
                </td>
                <td className="px-3 py-2.5 text-[12px] text-ink-2">
                  {file.date || <span className="text-ink-3">—</span>}
                </td>
                <td className="px-3 py-2.5 text-right text-[11px] tabular-nums text-ink-3">
                  {typeof file.size === "number" ? prettySize(file.size) : "—"}
                </td>
                <td className="px-3 py-2.5 text-right">
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      openOrganizedKey(fullKey);
                    }}
                    className="focus-ring text-ink-3 hover:text-ink-1"
                    title="Open in new tab"
                  >
                    <ExternalLink className="h-3.5 w-3.5" />
                  </button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </Card>
  );
}

/* ---------------- small atoms ---------------- */

function Chip({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={clsx(
        "focus-ring rounded-chip border px-2 py-0.5 text-[10px] font-medium transition-colors",
        active
          ? "border-accent/40 bg-accent text-white"
          : "border-border bg-surface text-ink-2 hover:bg-sunken hover:text-ink-1"
      )}
    >
      {children}
    </button>
  );
}

function GridSkeleton() {
  return (
    <div className="space-y-7">
      <div>
        <Skeleton className="mb-2.5 h-3 w-32" />
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-[68px]" />
          ))}
        </div>
      </div>
      <div>
        <Skeleton className="mb-2.5 h-3 w-32" />
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-[148px]" />
          ))}
        </div>
      </div>
    </div>
  );
}

function EmptyFolder({ isRoot }: { isRoot: boolean }) {
  return (
    <Card className="flex flex-col items-center px-6 py-14 text-center" variant="flat">
      <div className="grid h-11 w-11 place-items-center rounded-full bg-accent-soft text-accent-ink">
        {isRoot ? <Layers className="h-5 w-5" /> : <Folder className="h-5 w-5" />}
      </div>
      <div className="mt-3 font-display text-sm font-semibold text-ink-1">
        {isRoot ? "Nothing filed yet" : "This folder is empty"}
      </div>
      <div className="mt-1 max-w-sm text-[12px] text-ink-3">
        {isRoot
          ? "Drop documents into the Upload tab to populate the library."
          : "Try navigating up using the breadcrumb."}
      </div>
    </Card>
  );
}
