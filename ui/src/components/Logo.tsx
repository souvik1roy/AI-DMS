import clsx from "clsx";

interface Props {
  size?: "sm" | "md" | "lg";
  /** Show the full "AllysAI." wordmark. Default true (the brand is the
   * wordmark; we don't render a separate mark). */
  withWordmark?: boolean;
  /** Force a single fill colour instead of using `currentColor`. */
  fill?: string;
  className?: string;
}

const SIZE_PX: Record<NonNullable<Props["size"]>, { h: number; w: number; fs: number }> = {
  sm: { h: 22, w: 96,  fs: 18 },
  md: { h: 28, w: 122, fs: 22 },
  lg: { h: 40, w: 174, fs: 32 },
};

/**
 * AllysAI wordmark. Renders as a single SVG so it scales crisply, adopts the
 * current text colour (so it flips automatically in dark mode), and avoids any
 * webfont-load FOUC.
 */
export function Logo({ size = "md", withWordmark = true, fill, className }: Props) {
  const { h, w, fs } = SIZE_PX[size];
  // The period is intentionally rendered as a separate `<tspan>` so we can give
  // it a tiny accent treatment if desired in the future.
  return (
    <span
      className={clsx("inline-flex items-center text-ink-1", className)}
      aria-label="AllysAI"
    >
      {withWordmark ? (
        <svg
          width={w}
          height={h}
          viewBox={`0 0 ${w} ${h}`}
          xmlns="http://www.w3.org/2000/svg"
          aria-hidden
        >
          <text
            x="0"
            y={h * 0.78}
            fill={fill ?? "currentColor"}
            fontFamily='"Geist","Inter","Helvetica Neue",Helvetica,Arial,sans-serif'
            fontWeight={800}
            fontSize={fs}
            letterSpacing="-0.025em"
          >
            AllysAI<tspan>.</tspan>
          </text>
        </svg>
      ) : (
        <svg
          width={h}
          height={h}
          viewBox={`0 0 ${h} ${h}`}
          xmlns="http://www.w3.org/2000/svg"
          aria-hidden
        >
          <text
            x={h * 0.05}
            y={h * 0.78}
            fill={fill ?? "currentColor"}
            fontFamily='"Geist","Inter","Helvetica Neue",Helvetica,Arial,sans-serif'
            fontWeight={800}
            fontSize={fs}
            letterSpacing="-0.025em"
          >
            A<tspan>.</tspan>
          </text>
        </svg>
      )}
    </span>
  );
}
