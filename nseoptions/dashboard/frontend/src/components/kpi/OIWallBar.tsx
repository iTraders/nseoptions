import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { compact, num } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { AnalyticsOut, WallPoint } from "@/types/contract";

interface SectionProps {
  title: string;
  walls: WallPoint[];
  max: number;
  tone: "call" | "put";
}

function WallSection({ title, walls, max, tone }: SectionProps) {
  return (
    <div className="space-y-1">
      <div className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">{title}</div>
      {walls.map((wall) => {
        const width = max > 0 ? Math.min(100, (wall.openInterest / max) * 100) : 0;
        return (
          <div key={wall.strikePrice} className="relative flex items-center justify-between rounded px-2 py-1 text-xs">
            <div
              className={cn("absolute inset-y-0 left-0 rounded", tone === "call" ? "bg-call/20" : "bg-put/20")}
              style={{ width: `${width}%` }}
            />
            <span className="relative font-mono font-medium">{num(wall.strikePrice, 0)}</span>
            <span className="relative font-mono text-muted-foreground">{compact(wall.openInterest)}</span>
          </div>
        );
      })}
    </div>
  );
}

/** Top open-interest walls: resistance (calls) above, support (puts) below. */
export function OIWallBar({ analytics }: { analytics: AnalyticsOut }) {
  const max = Math.max(
    1,
    ...analytics.support.map((w) => w.openInterest),
    ...analytics.resistance.map((w) => w.openInterest),
  );

  return (
    <Card>
      <CardHeader className="pb-1">
        <CardTitle>Support / Resistance</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <WallSection title="Resistance · Calls" walls={analytics.resistance} max={max} tone="put" />
        <WallSection title="Support · Puts" walls={analytics.support} max={max} tone="call" />
      </CardContent>
    </Card>
  );
}
