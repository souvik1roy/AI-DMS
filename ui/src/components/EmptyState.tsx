import clsx from "clsx";
import { type LucideIcon } from "lucide-react";

import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";

interface Props {
  icon: LucideIcon;
  title: string;
  body?: string;
  cta?: { label: string; onClick: () => void };
  className?: string;
}

export function EmptyState({ icon: Icon, title, body, cta, className }: Props) {
  return (
    <Card
      variant="flat"
      className={clsx(
        "flex flex-col items-center px-6 py-12 text-center border-dashed",
        className
      )}
    >
      <div className="grid h-12 w-12 place-items-center rounded-full bg-accent-soft text-accent-ink">
        <Icon className="h-5 w-5" />
      </div>
      <div className="mt-3 font-display text-sm font-semibold text-ink-1">{title}</div>
      {body && <div className="mt-1 max-w-sm text-[12px] leading-relaxed text-ink-3">{body}</div>}
      {cta && (
        <Button variant="primary" size="sm" className="mt-4" onClick={cta.onClick}>
          {cta.label}
        </Button>
      )}
    </Card>
  );
}
