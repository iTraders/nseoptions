import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { compact, num } from "@/lib/format";
import { cn } from "@/lib/utils";
import { useDashboardStore } from "@/store/dashboard";
import type { StrategyBias, Suggestion } from "@/types/contract";

const BIAS_VARIANT: Record<StrategyBias, "success" | "danger" | "warning" | "muted"> = {
  bullish: "success",
  bearish: "danger",
  volatile: "warning",
  neutral: "muted",
};

/** A single ranked strategy suggestion with rationale and a "load" action. */
export function SuggestionCard({ suggestion }: { suggestion: Suggestion }) {
  const loadLegs = useDashboardStore((state) => state.loadLegs);
  const hasLegs = suggestion.legs.length > 0;

  return (
    <Card className="flex flex-col">
      <CardHeader className="flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm">{suggestion.name}</CardTitle>
        <Badge variant={BIAS_VARIANT[suggestion.bias]}>{suggestion.bias}</Badge>
      </CardHeader>
      <CardContent className="flex flex-1 flex-col gap-3">
        {hasLegs ? (
          <div className="flex flex-wrap gap-1.5">
            {suggestion.legs.map((leg, index) => (
              <span
                key={index}
                className={cn(
                  "rounded px-1.5 py-0.5 font-mono text-[11px]",
                  leg.side === "BUY" ? "bg-profit/15 text-profit" : "bg-loss/15 text-loss",
                )}
              >
                {leg.side} {leg.qty}× {leg.strike}
                {leg.leg}
              </span>
            ))}
          </div>
        ) : null}

        {hasLegs ? (
          <div className="grid grid-cols-3 gap-2 text-xs">
            <div>
              <div className="text-muted-foreground">Max P</div>
              <div className="font-mono text-profit">
                {suggestion.max_profit === null ? "∞" : compact(suggestion.max_profit)}
              </div>
            </div>
            <div>
              <div className="text-muted-foreground">Max L</div>
              <div className="font-mono text-loss">
                {suggestion.max_loss === null ? "∞" : compact(suggestion.max_loss)}
              </div>
            </div>
            <div>
              <div className="text-muted-foreground">Breakeven</div>
              <div className="font-mono">
                {suggestion.breakevens.map((value) => num(value, 0)).join(", ") || "–"}
              </div>
            </div>
          </div>
        ) : null}

        <ul className="space-y-1 text-xs text-muted-foreground">
          {suggestion.rationale.map((reason, index) => (
            <li key={index} className="flex gap-1.5">
              <span className="text-primary">•</span>
              <span>{reason}</span>
            </li>
          ))}
        </ul>

        {hasLegs ? (
          <Button
            size="sm"
            variant="outline"
            className="mt-auto w-full"
            onClick={() => loadLegs(suggestion.legs)}
          >
            Open in Builder
          </Button>
        ) : null}
      </CardContent>
    </Card>
  );
}
