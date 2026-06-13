import {
  Area,
  AreaChart,
  CartesianGrid,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { compact, inr, num } from "@/lib/format";
import type { PayoffOut } from "@/types/contract";

const TOOLTIP_STYLE = {
  background: "hsl(var(--popover))",
  border: "1px solid hsl(var(--border))",
  borderRadius: 8,
  fontSize: 12,
  color: "hsl(var(--popover-foreground))",
} as const;

/** Expiry payoff curve, shaded green above breakeven and red below. */
export function PayoffChart({ payoff, spot }: { payoff: PayoffOut; spot: number }) {
  const data = payoff.curve.map((point) => ({ spot: point.spot, pnl: point.pnl }));
  const values = data.map((point) => point.pnl);
  const max = Math.max(...values, 0);
  const min = Math.min(...values, 0);
  const offset = max - min === 0 ? 0.5 : max / (max - min);

  return (
    <ResponsiveContainer width="100%" height={280}>
      <AreaChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: -4 }}>
        <defs>
          <linearGradient id="pnl-fill" x1="0" y1="0" x2="0" y2="1">
            <stop offset={0} stopColor="hsl(var(--profit))" stopOpacity={0.5} />
            <stop offset={offset} stopColor="hsl(var(--profit))" stopOpacity={0.05} />
            <stop offset={offset} stopColor="hsl(var(--loss))" stopOpacity={0.05} />
            <stop offset={1} stopColor="hsl(var(--loss))" stopOpacity={0.5} />
          </linearGradient>
          <linearGradient id="pnl-stroke" x1="0" y1="0" x2="0" y2="1">
            <stop offset={offset} stopColor="hsl(var(--profit))" />
            <stop offset={offset} stopColor="hsl(var(--loss))" />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" strokeOpacity={0.4} />
        <XAxis
          dataKey="spot"
          type="number"
          domain={["dataMin", "dataMax"]}
          tick={{ fontSize: 10 }}
          stroke="hsl(var(--muted-foreground))"
          tickFormatter={(value) => num(value, 0)}
          minTickGap={40}
        />
        <YAxis
          tick={{ fontSize: 10 }}
          stroke="hsl(var(--muted-foreground))"
          width={52}
          tickFormatter={(value) => compact(value)}
        />
        <Tooltip
          contentStyle={TOOLTIP_STYLE}
          formatter={(value) => [inr(value as number), "P/L at expiry"]}
          labelFormatter={(label) => `Spot ${num(label as number, 0)}`}
        />
        <ReferenceLine y={0} stroke="hsl(var(--muted-foreground))" />
        <ReferenceLine
          x={spot}
          stroke="hsl(var(--foreground))"
          strokeDasharray="4 3"
          label={{ value: "Spot", fontSize: 10, fill: "hsl(var(--foreground))", position: "insideTopRight" }}
        />
        {payoff.breakevens.map((breakeven) => (
          <ReferenceLine key={breakeven} x={breakeven} stroke="hsl(var(--atm))" strokeDasharray="2 2" />
        ))}
        <Area type="monotone" dataKey="pnl" stroke="url(#pnl-stroke)" strokeWidth={2} fill="url(#pnl-fill)" />
      </AreaChart>
    </ResponsiveContainer>
  );
}
