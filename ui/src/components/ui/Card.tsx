import { forwardRef, type HTMLAttributes } from "react";
import clsx from "clsx";

type Variant = "flat" | "raised" | "interactive";

interface Props extends HTMLAttributes<HTMLDivElement> {
  variant?: Variant;
  as?: "div" | "section" | "article";
}

const VARIANT: Record<Variant, string> = {
  flat: "bg-surface border border-border",
  raised: "bg-surface border border-border shadow-elev-1",
  interactive:
    "bg-surface border border-border shadow-elev-1 transition-all duration-200 ease-spring " +
    "hover:-translate-y-0.5 hover:shadow-elev-2 hover:border-accent/40",
};

export const Card = forwardRef<HTMLDivElement, Props>(function Card(
  { variant = "raised", as: As = "div", className, ...rest },
  ref
) {
  return (
    <As
      ref={ref as never}
      className={clsx("rounded-card", VARIANT[variant], className)}
      {...rest}
    />
  );
});

export function CardHeader({
  title,
  subtitle,
  trailing,
  className,
}: {
  title: React.ReactNode;
  subtitle?: React.ReactNode;
  trailing?: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={clsx("flex items-start justify-between gap-3 px-5 pt-4", className)}>
      <div className="min-w-0">
        <div className="font-display text-[15px] font-semibold tracking-tight text-ink-1">
          {title}
        </div>
        {subtitle && (
          <div className="mt-0.5 text-[12px] text-ink-3">{subtitle}</div>
        )}
      </div>
      {trailing}
    </div>
  );
}

export function CardBody({
  className,
  children,
}: {
  className?: string;
  children: React.ReactNode;
}) {
  return <div className={clsx("p-5", className)}>{children}</div>;
}
