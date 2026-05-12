import { Loader2 } from "lucide-react";
import {
  forwardRef,
  type ButtonHTMLAttributes,
  type ReactNode,
} from "react";
import clsx from "clsx";

type Variant = "primary" | "secondary" | "ghost" | "danger";
type Size = "sm" | "md" | "lg";

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  loading?: boolean;
  leftIcon?: ReactNode;
  rightIcon?: ReactNode;
}

const VARIANT: Record<Variant, string> = {
  primary:
    "bg-accent text-white hover:bg-accent/90 active:bg-accent shadow-elev-1 disabled:bg-ink-3",
  secondary:
    "bg-surface text-ink-1 border border-border hover:bg-sunken disabled:text-ink-3",
  ghost:
    "bg-transparent text-ink-2 hover:bg-sunken hover:text-ink-1 disabled:text-ink-3",
  danger:
    "bg-rose-600 text-white hover:bg-rose-700 active:bg-rose-700 disabled:bg-rose-300",
};

const SIZE: Record<Size, string> = {
  sm: "h-7 px-2.5 text-[12px] gap-1.5",
  md: "h-9 px-3.5 text-[13px] gap-2",
  lg: "h-10 px-4 text-sm gap-2",
};

export const Button = forwardRef<HTMLButtonElement, Props>(function Button(
  {
    variant = "secondary",
    size = "md",
    loading = false,
    disabled,
    leftIcon,
    rightIcon,
    className,
    children,
    ...rest
  },
  ref
) {
  return (
    <button
      ref={ref}
      disabled={disabled || loading}
      className={clsx(
        "focus-ring inline-flex items-center justify-center rounded-md font-medium",
        "transition-all duration-150 ease-spring",
        "disabled:cursor-not-allowed disabled:opacity-70",
        VARIANT[variant],
        SIZE[size],
        className
      )}
      {...rest}
    >
      {loading ? (
        <Loader2 className="h-3.5 w-3.5 animate-spin" />
      ) : (
        leftIcon
      )}
      {children}
      {!loading && rightIcon}
    </button>
  );
});
