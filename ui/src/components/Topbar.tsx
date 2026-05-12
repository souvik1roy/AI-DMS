import { HelpCircle, Search } from "lucide-react";
import clsx from "clsx";
import { type ReactNode } from "react";

import { Kbd } from "@/components/ui/Kbd";

interface Props {
  title: ReactNode;
  subtitle?: ReactNode;
  trailing?: ReactNode;
  showSearch?: boolean;
  onSearchClick?: () => void;
  className?: string;
}

export function Topbar({
  title,
  subtitle,
  trailing,
  showSearch = true,
  onSearchClick,
  className,
}: Props) {
  return (
    <div
      className={clsx(
        "sticky top-0 z-30 flex items-center gap-4 border-b border-border bg-canvas/80 px-6 py-3 backdrop-blur",
        className
      )}
    >
      <div className="min-w-0 flex-1">
        <div className="truncate font-display text-[15px] font-semibold tracking-tight text-ink-1">
          {title}
        </div>
        {subtitle && (
          <div className="truncate text-[12px] text-ink-3">{subtitle}</div>
        )}
      </div>
      {showSearch && (
        <button
          onClick={onSearchClick}
          className="focus-ring hidden items-center gap-2 rounded-md border border-border bg-surface px-2.5 py-1.5 text-[12px] text-ink-3 hover:text-ink-2 md:inline-flex"
        >
          <Search className="h-3.5 w-3.5" />
          Quick search
          <span className="ml-2 flex items-center gap-0.5 text-ink-3">
            <Kbd>⌘</Kbd>
            <Kbd>K</Kbd>
          </span>
        </button>
      )}
      <button
        className="focus-ring grid h-8 w-8 place-items-center rounded-md text-ink-3 hover:bg-sunken hover:text-ink-1"
        title="Help & shortcuts"
      >
        <HelpCircle className="h-4 w-4" />
      </button>
      {trailing}
    </div>
  );
}
