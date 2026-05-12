import clsx from "clsx";
import { type ReactNode, useState } from "react";

interface Props {
  label: string;
  side?: "top" | "bottom" | "left" | "right";
  children: ReactNode;
  className?: string;
}

const SIDE: Record<NonNullable<Props["side"]>, string> = {
  top: "bottom-[calc(100%+6px)] left-1/2 -translate-x-1/2",
  bottom: "top-[calc(100%+6px)] left-1/2 -translate-x-1/2",
  left: "right-[calc(100%+6px)] top-1/2 -translate-y-1/2",
  right: "left-[calc(100%+6px)] top-1/2 -translate-y-1/2",
};

/** Minimal hover/focus tooltip — CSS-only positioning, no JS portal. */
export function Tooltip({ label, side = "top", children, className }: Props) {
  const [open, setOpen] = useState(false);
  return (
    <span
      className={clsx("relative inline-flex", className)}
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
      onFocus={() => setOpen(true)}
      onBlur={() => setOpen(false)}
    >
      {children}
      {open && (
        <span
          role="tooltip"
          className={clsx(
            "pointer-events-none absolute z-50 whitespace-nowrap rounded-md border border-border bg-surface px-2 py-1 text-[11px] font-medium text-ink-1 shadow-elev-2",
            SIDE[side]
          )}
        >
          {label}
        </span>
      )}
    </span>
  );
}
