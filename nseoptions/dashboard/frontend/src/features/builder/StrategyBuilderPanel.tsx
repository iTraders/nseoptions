import { PayoffChart } from "@/components/builder/PayoffChart";
import { PayoffSummary } from "@/components/builder/PayoffSummary";
import { StrategyLegEditor } from "@/components/builder/StrategyLegEditor";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useChain } from "@/hooks/useChain";
import { usePayoff } from "@/hooks/usePayoff";
import { useDashboardStore } from "@/store/dashboard";
import type { PayoffIn } from "@/types/contract";

/** Feature III: multi-leg strategy builder with the expiry payoff diagram. */
export function StrategyBuilderPanel({ expiry }: { expiry?: string }) {
  const { data: chain } = useChain(expiry);
  const symbol = useDashboardStore((state) => state.symbol);
  const builderLegs = useDashboardStore((state) => state.builderLegs);

  const input: PayoffIn | null =
    expiry && builderLegs.length > 0 ? { symbol, expiry, lots: 1, legs: builderLegs } : null;
  const { data: payoff } = usePayoff(input);

  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,430px)_minmax(0,1fr)]">
      <Card>
        <CardHeader className="pb-2">
          <CardTitle>Strategy Legs</CardTitle>
        </CardHeader>
        <CardContent>
          <StrategyLegEditor chain={chain} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle>Payoff at Expiry</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {payoff && chain ? (
            <>
              <PayoffChart payoff={payoff} spot={chain.underlying} />
              <PayoffSummary payoff={payoff} />
            </>
          ) : (
            <div className="flex h-72 items-center justify-center text-sm text-muted-foreground">
              Add at least one leg to see the payoff diagram.
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
