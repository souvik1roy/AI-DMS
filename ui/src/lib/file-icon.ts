import {
  FileAudio,
  FileImage,
  FileSpreadsheet,
  FileText,
  FileType,
  FileVideo,
  Presentation,
  type LucideIcon,
} from "lucide-react";

export interface IconSpec {
  Icon: LucideIcon;
  bg: string;
  fg: string;
  kind:
    | "image"
    | "audio"
    | "video"
    | "spreadsheet"
    | "slides"
    | "doc"
    | "pdf";
  label: string;
}

/** Per-modality colour + icon picker for files surfaced anywhere in the UI. */
export function iconFor(name: string, contentType?: string | null): IconSpec {
  const lower = (name || "").toLowerCase();
  const ct = (contentType || "").toLowerCase();

  if (ct.startsWith("image/") || /\.(png|jpe?g|heic|tiff?|gif|webp|svg)$/i.test(lower))
    return {
      Icon: FileImage,
      bg: "bg-purple-50 dark:bg-purple-950/40",
      fg: "text-purple-600 dark:text-purple-300",
      kind: "image",
      label: "Image",
    };
  if (ct.startsWith("audio/") || /\.(mp3|wav|m4a|ogg|flac|aac)$/i.test(lower))
    return {
      Icon: FileAudio,
      bg: "bg-amber-50 dark:bg-amber-950/40",
      fg: "text-amber-700 dark:text-amber-300",
      kind: "audio",
      label: "Audio",
    };
  if (ct.startsWith("video/") || /\.(mp4|mov|mkv|webm|avi)$/i.test(lower))
    return {
      Icon: FileVideo,
      bg: "bg-rose-50 dark:bg-rose-950/40",
      fg: "text-rose-700 dark:text-rose-300",
      kind: "video",
      label: "Video",
    };
  if (/\.(xls|xlsx|ods|csv|tsv)$/i.test(lower))
    return {
      Icon: FileSpreadsheet,
      bg: "bg-emerald-50 dark:bg-emerald-950/40",
      fg: "text-emerald-700 dark:text-emerald-300",
      kind: "spreadsheet",
      label: "Spreadsheet",
    };
  if (/\.(ppt|pptx|odp)$/i.test(lower))
    return {
      Icon: Presentation,
      bg: "bg-sky-50 dark:bg-sky-950/40",
      fg: "text-sky-700 dark:text-sky-300",
      kind: "slides",
      label: "Slides",
    };
  if (/\.(doc|docx|odt|txt|rtf)$/i.test(lower))
    return {
      Icon: FileType,
      bg: "bg-indigo-50 dark:bg-indigo-950/40",
      fg: "text-indigo-700 dark:text-indigo-300",
      kind: "doc",
      label: "Document",
    };
  return {
    Icon: FileText,
    bg: "bg-accent-soft",
    fg: "text-accent-ink",
    kind: "pdf",
    label: "PDF",
  };
}
