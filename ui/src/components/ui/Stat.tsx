import clsx from "clsx";
import { ArrowDownRight, ArrowUpRight, Minus, type LucideIcon } from "lucide-react";

interface Props {
  label: string;
  value: number | string;
  hint?: string;
  trend?: { delta: number; suffix?: string } | null;
  icon?: LucideIcon;
  className?: string;
}

export function Stat({ label, value, hint, trend, icon: Icon, className }: Props) {
  return (
    <div
      className={clsx(
        "rounded-card border border-border bg-surface p-5 shadow-elev-1",
        className
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="text-[11px] uppercase tracking-wider text-ink-3">{label}</div>
        {Icon && (
          <div className="grid h-7 w-7 place-items-center rounded-md bg-accent-soft text-accent-ink">
            <Icon className="h-3.5 w-3.5" />
          </div>
        )}
      </div>
      <div className="mt-3 flex items-baseline gap-2">
        <div className="font-display text-[28px] font-semibold leading-none tracking-tight text-ink-1 tabular-nums">
          {value}
        </div>
        {trend && <TrendChip {...trend} />}
      </div>
      {hint && <div className="mt-1.5 text-[12px] text-ink-3">{hint}</div>}
    </div>
  );
}

function TrendChip({ delta, suffix }: { delta: number; suffix?: string }) {
  if (delta === 0) {
    return (
      <span className="inline-flex items-center gap-0.5 rounded-chip bg-sunken px-1.5 py-0.5 text-[10px] font-medium text-ink-2">
        <Minus className="h-3 w-3" />
        flat
      </span>
    );
  }
  const positive = delta > 0;
  return (
    <span
      className={clsx(
        "inline-flex items-center gap-0.5 rounded-chip px-1.5 py-0.5 text-[10px] font-medium",
        positive
          ? "bg-accent-soft text-accent-ink"
          : "bg-rose-50 text-rose-700 dark:bg-rose-950/40 dark:text-rose-300"
      )}
    >
      {positive ? (
        <ArrowUpRight className="h-3 w-3" />
      ) : (
        <ArrowDownRight className="h-3 w-3" />
      )}
      {Math.abs(delta)}
      {suffix}
    </span>
  );
}
