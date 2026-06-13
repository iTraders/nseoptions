import { KpiStat } from "@/components/kpi/KpiStat";
import { inr, num } from "@/lib/format";
import type { PayoffOut } from "@/types/contract";

/** Headline strategy metrics: max P/L, breakevens and net greeks. */
export function PayoffSummary({ payoff }: { payoff: PayoffOut }) {
  const greeks = payoff.net_greeks;
  const breakevens = payoff.breakevens.length
    ? payoff.breakevens.map((value) => num(value, 0)).join(", ")
    : "–";

  return (
    <div className="space-y-2">
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
        <KpiStat
          label="Max Profit"
          value={payoff.max_profit === null ? "Unlimited" : inr(payoff.max_profit)}
          tone="profit"
        />
        <KpiStat
          label="Max Loss"
          value={payoff.max_loss === null ? "Unlimited" : inr(payoff.max_loss)}
          tone="loss"
        />
        <KpiStat label="Breakeven(s)" value={breakevens} />
        <KpiStat label="Net Delta" value={num(greeks.delta)} />
        <KpiStat label="Theta / day" value={num(greeks.theta)} />
        <KpiStat label="Vega" value={num(greeks.vega)} />
      </div>
      {payoff.estimated ? (
        <p className="text-[11px] text-muted-foreground">
          * premiums estimated from the live LTP where not specified.
        </p>
      ) : null}
    </div>
  );
}
