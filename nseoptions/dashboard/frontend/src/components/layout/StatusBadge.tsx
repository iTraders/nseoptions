import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { ChainConnection } from "@/hooks/useChainSocket";

/** A live-feed status pill (Live / Degraded / Connecting / Disconnected). */
export function StatusBadge({ state, feed }: ChainConnection) {
  const connected = state === "open";
  const live = connected && feed === "live";

  const variant = live ? "success" : connected ? "warning" : "danger";
  const label = !connected
    ? "Disconnected"
    : feed === "live"
      ? "Live"
      : feed === "degraded"
        ? "Degraded"
        : "Connecting";

  return (
    <Badge variant={variant} className="gap-1.5">
      <span
        className={cn(
          "h-2 w-2 rounded-full",
          live ? "animate-pulse bg-profit" : connected ? "bg-atm" : "bg-loss",
        )}
      />
      {label}
    </Badge>
  );
}
