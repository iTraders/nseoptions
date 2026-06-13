import { Plus, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useDashboardStore } from "@/store/dashboard";
import type { ChainOut, LegQuote, OptionLeg } from "@/types/contract";

function quoteFor(chain: ChainOut | undefined, strike: number, leg: OptionLeg): LegQuote | null {
  const row = chain?.rows.find((r) => r.strikePrice === strike);
  return (leg === "CE" ? row?.ce : row?.pe) ?? null;
}

/** Add / edit / remove the legs of a multi-leg option strategy. */
export function StrategyLegEditor({ chain }: { chain?: ChainOut }) {
  const { builderLegs, addLeg, updateLeg, removeLeg, clearLegs } = useDashboardStore();

  const strikes = chain?.rows.map((r) => r.strikePrice) ?? [];
  const atm = chain?.atm ?? strikes[Math.floor(strikes.length / 2)] ?? 0;

  const addDefault = () =>
    addLeg({ strike: atm, leg: "CE", side: "BUY", qty: 1, price: quoteFor(chain, atm, "CE")?.lastPrice ?? null });

  return (
    <div className="space-y-2">
      {builderLegs.length === 0 ? (
        <p className="rounded-md border border-dashed p-4 text-center text-sm text-muted-foreground">
          Add legs to build a strategy, or load one from the Suggestions tab.
        </p>
      ) : null}

      {builderLegs.map((leg, index) => (
        <div key={index} className="flex flex-wrap items-center gap-2 rounded-md border p-2">
          <Button
            size="sm"
            variant={leg.side === "BUY" ? "default" : "destructive"}
            className="w-16"
            onClick={() => updateLeg(index, { side: leg.side === "BUY" ? "SELL" : "BUY" })}
          >
            {leg.side}
          </Button>

          <Input
            type="number"
            min={1}
            value={leg.qty}
            onChange={(event) => updateLeg(index, { qty: Math.max(1, Number(event.target.value) || 1) })}
            className="w-16"
            aria-label="Lots"
          />

          <Select
            value={String(leg.strike)}
            onValueChange={(value) => {
              const strike = Number(value);
              updateLeg(index, { strike, price: quoteFor(chain, strike, leg.leg)?.lastPrice ?? leg.price });
            }}
          >
            <SelectTrigger className="w-28 font-mono">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {strikes.map((strike) => (
                <SelectItem key={strike} value={String(strike)} className="font-mono">
                  {strike}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          <Button
            size="sm"
            variant="outline"
            className="w-12"
            onClick={() => {
              const next: OptionLeg = leg.leg === "CE" ? "PE" : "CE";
              updateLeg(index, { leg: next, price: quoteFor(chain, leg.strike, next)?.lastPrice ?? leg.price });
            }}
          >
            {leg.leg}
          </Button>

          <Input
            type="number"
            step="0.05"
            value={leg.price ?? ""}
            onChange={(event) =>
              updateLeg(index, { price: event.target.value === "" ? null : Number(event.target.value) })
            }
            className="w-24"
            placeholder="LTP"
            aria-label="Premium"
          />

          <Button
            size="icon"
            variant="ghost"
            className="ml-auto"
            onClick={() => removeLeg(index)}
            aria-label="Remove leg"
          >
            <Trash2 className="h-4 w-4 text-loss" />
          </Button>
        </div>
      ))}

      <div className="flex gap-2">
        <Button size="sm" variant="outline" onClick={addDefault}>
          <Plus className="h-4 w-4" /> Add leg
        </Button>
        {builderLegs.length > 0 ? (
          <Button size="sm" variant="ghost" onClick={clearLegs}>
            Clear all
          </Button>
        ) : null}
      </div>
    </div>
  );
}
