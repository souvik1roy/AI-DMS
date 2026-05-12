import clsx from "clsx";

export function Kbd({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <kbd
      className={clsx(
        "inline-flex h-[18px] min-w-[18px] items-center justify-center rounded border border-border bg-surface px-1 font-mono text-[10px] font-medium text-ink-2",
        className
      )}
    >
      {children}
    </kbd>
  );
}
