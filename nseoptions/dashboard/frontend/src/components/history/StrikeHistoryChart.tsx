import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { clock, compact } from "@/lib/format";
import type { HistoryOut } from "@/types/contract";

const TOOLTIP_STYLE = {
  background: "hsl(var(--popover))",
  border: "1px solid hsl(var(--border))",
  borderRadius: 8,
  fontSize: 12,
  color: "hsl(var(--popover-foreground))",
} as const;

/** Time series of one tracked field for a single strike-leg. */
export function StrikeHistoryChart({ history }: { history: HistoryOut }) {
  const data = history.points.map((point) => ({ time: clock(point.ts), value: point.value }));

  if (data.length < 2) {
    return (
      <div className="flex h-64 flex-col items-center justify-center gap-1 text-sm text-muted-foreground">
        <span>Not enough history yet.</span>
        <span className="text-xs">A point is recorded on every poll — the series fills in as the market ticks.</span>
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={300}>
      <AreaChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
        <defs>
          <linearGradient id="hist-fill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="hsl(var(--primary))" stopOpacity={0.35} />
            <stop offset="100%" stopColor="hsl(var(--primary))" stopOpacity={0.02} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" strokeOpacity={0.4} />
        <XAxis dataKey="time" tick={{ fontSize: 10 }} stroke="hsl(var(--muted-foreground))" minTickGap={40} />
        <YAxis
          tick={{ fontSize: 10 }}
          stroke="hsl(var(--muted-foreground))"
          width={52}
          tickFormatter={(value) => compact(value)}
          domain={["auto", "auto"]}
        />
        <Tooltip
          contentStyle={TOOLTIP_STYLE}
          formatter={(value) => [compact(value as number), history.field.toUpperCase()]}
        />
        <Area type="monotone" dataKey="value" stroke="hsl(var(--primary))" strokeWidth={2} fill="url(#hist-fill)" />
      </AreaChart>
    </ResponsiveContainer>
  );
}
