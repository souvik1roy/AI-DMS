import clsx from "clsx";
import { type ReactNode } from "react";

type Tone = "neutral" | "accent" | "amber" | "rose" | "sky" | "indigo" | "purple" | "emerald";
type Size = "sm" | "md";

interface Props {
  tone?: Tone;
  size?: Size;
  variant?: "solid" | "outline";
  className?: string;
  children: ReactNode;
}

const SOLID: Record<Tone, string> = {
  neutral: "bg-sunken text-ink-2",
  accent:  "bg-accent-soft text-accent-ink",
  amber:   "bg-amber-50 text-amber-700 dark:bg-amber-950/50 dark:text-amber-300",
  rose:    "bg-rose-50 text-rose-700 dark:bg-rose-950/50 dark:text-rose-300",
  sky:     "bg-sky-50 text-sky-700 dark:bg-sky-950/50 dark:text-sky-300",
  indigo:  "bg-indigo-50 text-indigo-700 dark:bg-indigo-950/50 dark:text-indigo-300",
  purple:  "bg-purple-50 text-purple-700 dark:bg-purple-950/50 dark:text-purple-300",
  emerald: "bg-emerald-50 text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-300",
};

const OUTLINE: Record<Tone, string> = {
  neutral: "border border-border text-ink-2 bg-transparent",
  accent:  "border border-accent/40 text-accent-ink bg-transparent",
  amber:   "border border-amber-300/60 text-amber-700 bg-transparent",
  rose:    "border border-rose-300/60 text-rose-700 bg-transparent",
  sky:     "border border-sky-300/60 text-sky-700 bg-transparent",
  indigo:  "border border-indigo-300/60 text-indigo-700 bg-transparent",
  purple:  "border border-purple-300/60 text-purple-700 bg-transparent",
  emerald: "border border-emerald-300/60 text-emerald-700 bg-transparent",
};

const SIZE: Record<Size, string> = {
  sm: "h-5 px-1.5 text-[10px]",
  md: "h-6 px-2 text-[11px]",
};

export function Badge({
  tone = "neutral",
  size = "md",
  variant = "solid",
  className,
  children,
}: Props) {
  const palette = variant === "solid" ? SOLID[tone] : OUTLINE[tone];
  return (
    <span
      className={clsx(
        "inline-flex items-center gap-1 rounded-chip font-medium leading-none",
        palette,
        SIZE[size],
        className
      )}
    >
      {children}
    </span>
  );
}
