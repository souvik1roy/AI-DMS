export function prettySize(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  if (n < 1024 * 1024 * 1024) return `${(n / (1024 * 1024)).toFixed(1)} MB`;
  return `${(n / (1024 * 1024 * 1024)).toFixed(1)} GB`;
}

/** Replace `_` with spaces so sanitised folder/file names look readable. */
export function prettyFolderName(name: string): string {
  return name.replace(/_+/g, " ").trim();
}

export function relativeTime(ms: number): string {
  const diff = Date.now() - ms;
  if (diff < 60_000) return "just now";
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)} min ago`;
  if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)} h ago`;
  if (diff < 7 * 86_400_000) return `${Math.floor(diff / 86_400_000)} d ago`;
  return new Date(ms).toLocaleDateString();
}

// Deterministic palette so the same document_type always lands on the same chip
// colour across the app.
const _TYPE_PALETTE = [
  "bg-accent-soft text-accent-ink",
  "bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300",
  "bg-amber-50 text-amber-700 dark:bg-amber-950/40 dark:text-amber-300",
  "bg-sky-50 text-sky-700 dark:bg-sky-950/40 dark:text-sky-300",
  "bg-purple-50 text-purple-700 dark:bg-purple-950/40 dark:text-purple-300",
  "bg-rose-50 text-rose-700 dark:bg-rose-950/40 dark:text-rose-300",
  "bg-indigo-50 text-indigo-700 dark:bg-indigo-950/40 dark:text-indigo-300",
  "bg-teal-50 text-teal-700 dark:bg-teal-950/40 dark:text-teal-300",
];

export function typeChipColor(type: string): string {
  let h = 0;
  for (let i = 0; i < type.length; i++) h = (h * 31 + type.charCodeAt(i)) | 0;
  return _TYPE_PALETTE[Math.abs(h) % _TYPE_PALETTE.length];
}
