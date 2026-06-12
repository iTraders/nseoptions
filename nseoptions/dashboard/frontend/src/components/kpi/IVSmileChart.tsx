import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { num } from "@/lib/format";
import type { AnalyticsOut } from "@/types/contract";

const TOOLTIP_STYLE = {
  background: "hsl(var(--popover))",
  border: "1px solid hsl(var(--border))",
  borderRadius: 8,
  fontSize: 12,
  color: "hsl(var(--popover-foreground))",
} as const;

/** The CE/PE implied-volatility smile across strikes. */
export function IVSmileChart({ analytics }: { analytics: AnalyticsOut }) {
  const data = analytics.iv_smile
    .filter((point) => point.ce_iv > 0 || point.pe_iv > 0)
    .map((point) => ({
      strike: point.strikePrice,
      call: point.ce_iv || null,
      put: point.pe_iv || null,
    }));

  return (
    <Card>
      <CardHeader className="pb-1">
        <CardTitle>IV Smile</CardTitle>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={170}>
          <LineChart data={data} margin={{ top: 6, right: 8, bottom: 0, left: -18 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" strokeOpacity={0.4} />
            <XAxis
              dataKey="strike"
              type="number"
              domain={["dataMin", "dataMax"]}
              tick={{ fontSize: 10 }}
              stroke="hsl(var(--muted-foreground))"
              tickFormatter={(value) => num(value, 0)}
              minTickGap={32}
            />
            <YAxis tick={{ fontSize: 10 }} stroke="hsl(var(--muted-foreground))" width={32} />
            <Tooltip
              contentStyle={TOOLTIP_STYLE}
              formatter={(value, name) => [`${num(value as number)}%`, name === "call" ? "Call IV" : "Put IV"]}
              labelFormatter={(label) => `Strike ${num(label as number, 0)}`}
            />
            <Legend wrapperStyle={{ fontSize: 11 }} iconType="plainline" />
            <ReferenceLine x={analytics.underlying} stroke="hsl(var(--foreground))" strokeOpacity={0.3} />
            <Line type="monotone" dataKey="call" name="Call IV" stroke="hsl(var(--call))" strokeWidth={2} dot={false} connectNulls />
            <Line type="monotone" dataKey="put" name="Put IV" stroke="hsl(var(--put))" strokeWidth={2} dot={false} connectNulls />
          </LineChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}
