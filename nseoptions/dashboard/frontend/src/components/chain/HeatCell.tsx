import { heatColor, textColorFor } from "@/lib/heatmap";
import { cn } from "@/lib/utils";

interface HeatCellProps {
  /** Normalized intensity in [0,1]; 0 -> red, 0.5 -> yellow, 1 -> green. */
  t: number;
  children: React.ReactNode;
  className?: string;
  /** When false the heat background is suppressed (e.g. a missing leg). */
  active?: boolean;
}

/**
 * A heat-map cell reproducing the Excel template's 3-colour scale
 * (#F8696B -> #FFEB84 -> #63BE7B). Purely presentational so it can be
 * covered by a deterministic visual snapshot test.
 */
export function HeatCell({ t, children, className, active = true }: HeatCellProps) {
  if (!active) {
    return (
      <span className={cn("block px-2 py-1 text-right tabular-nums text-muted-foreground", className)}>
        {children}
      </span>
    );
  }

  const background = heatColor(t);
  return (
    <span
      className={cn("block px-2 py-1 text-right font-medium tabular-nums", className)}
      style={{ backgroundColor: background, color: textColorFor(background) }}
    >
      {children}
    </span>
  );
}
