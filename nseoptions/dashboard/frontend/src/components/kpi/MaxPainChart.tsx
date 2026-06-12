import {
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { compact, num } from "@/lib/format";
import type { AnalyticsOut } from "@/types/contract";

const TOOLTIP_STYLE = {
  background: "hsl(var(--popover))",
  border: "1px solid hsl(var(--border))",
  borderRadius: 8,
  fontSize: 12,
  color: "hsl(var(--popover-foreground))",
} as const;

/** The option-writer loss curve with max-pain and spot reference lines. */
export function MaxPainChart({ analytics }: { analytics: AnalyticsOut }) {
  const data = analytics.loss_by_strike.map((point) => ({
    strike: point.strikePrice,
    loss: point.loss,
  }));

  return (
    <Card>
      <CardHeader className="pb-1">
        <CardTitle>
          Max Pain{analytics.max_pain ? ` · ${num(analytics.max_pain, 0)}` : ""}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={160}>
          <LineChart data={data} margin={{ top: 6, right: 8, bottom: 0, left: 0 }}>
            <XAxis
              dataKey="strike"
              type="number"
              domain={["dataMin", "dataMax"]}
              tick={{ fontSize: 10 }}
              stroke="hsl(var(--muted-foreground))"
              tickFormatter={(value) => num(value, 0)}
              minTickGap={32}
            />
            <YAxis hide domain={["dataMin", "dataMax"]} />
            <Tooltip
              contentStyle={TOOLTIP_STYLE}
              formatter={(value) => [compact(value as number), "Writer loss"]}
              labelFormatter={(label) => `Strike ${num(label as number, 0)}`}
            />
            {analytics.max_pain ? (
              <ReferenceLine
                x={analytics.max_pain}
                stroke="hsl(var(--atm))"
                strokeDasharray="4 3"
                label={{ value: "MP", fontSize: 10, fill: "hsl(var(--atm))", position: "top" }}
              />
            ) : null}
            <ReferenceLine x={analytics.underlying} stroke="hsl(var(--foreground))" strokeOpacity={0.35} />
            <Line type="monotone" dataKey="loss" stroke="hsl(var(--primary))" strokeWidth={2} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}
