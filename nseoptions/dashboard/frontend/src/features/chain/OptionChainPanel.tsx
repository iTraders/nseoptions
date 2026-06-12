import { OptionChainTable } from "@/components/chain/OptionChainTable";
import { IVSmileChart } from "@/components/kpi/IVSmileChart";
import { KpiStat } from "@/components/kpi/KpiStat";
import { MaxPainChart } from "@/components/kpi/MaxPainChart";
import { OIWallBar } from "@/components/kpi/OIWallBar";
import { PCRGauge } from "@/components/kpi/PCRGauge";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useAnalytics } from "@/hooks/useAnalytics";
import { useChain } from "@/hooks/useChain";
import { compact, inr, num } from "@/lib/format";
import { useDashboardStore } from "@/store/dashboard";

function ChainSkeleton() {
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-3 gap-3 lg:grid-cols-6">
        {Array.from({ length: 6 }).map((_, index) => (
          <Skeleton key={index} className="h-16" />
        ))}
      </div>
      <Skeleton className="h-[60vh] w-full" />
    </div>
  );
}

/** Feature I: the live option chain + KPI strip + analytics sidebar. */
export function OptionChainPanel({ expiry }: { expiry?: string }) {
  const { data: chain, isLoading, isError } = useChain(expiry);
  const { data: analytics } = useAnalytics(expiry);
  const selectedStrike = useDashboardStore((state) => state.selectedStrike);
  const setSelectedStrike = useDashboardStore((state) => state.setSelectedStrike);

  if (isError) {
    return (
      <Card>
        <CardContent className="flex h-64 items-center justify-center text-sm text-muted-foreground">
          Waiting for the live feed — the backend may still be priming the NSE session.
        </CardContent>
      </Card>
    );
  }

  if (isLoading || !chain) return <ChainSkeleton />;

  const pcrTone = chain.put_call_ratio >= 1 ? "profit" : "loss";

  return (
    <div className="space-y-4 animate-fade-in">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        <KpiStat label="Spot" value={inr(chain.underlying)} />
        <KpiStat label="PCR" value={chain.put_call_ratio.toFixed(2)} tone={pcrTone} />
        <KpiStat label="Max Pain" value={analytics?.max_pain ? num(analytics.max_pain, 0) : "–"} />
        <KpiStat label="ATM" value={num(chain.atm, 0)} />
        <KpiStat label="Total OI Call" value={compact(chain.tot_oi_ce)} tone="call" />
        <KpiStat label="Total OI Put" value={compact(chain.tot_oi_pe)} tone="put" />
      </div>

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_330px]">
        <OptionChainTable
          chain={chain}
          selectedStrike={selectedStrike}
          onSelectStrike={setSelectedStrike}
        />
        <div className="space-y-4">
          <PCRGauge pcr={chain.put_call_ratio} />
          {analytics ? <MaxPainChart analytics={analytics} /> : null}
          {analytics ? <IVSmileChart analytics={analytics} /> : null}
          {analytics ? <OIWallBar analytics={analytics} /> : null}
        </div>
      </div>
    </div>
  );
}
