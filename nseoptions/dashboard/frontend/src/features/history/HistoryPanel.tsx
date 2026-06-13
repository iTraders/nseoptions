import { useState } from "react";

import { StrikeHistoryChart } from "@/components/history/StrikeHistoryChart";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useChain } from "@/hooks/useChain";
import { useHistory } from "@/hooks/useHistory";
import { cn } from "@/lib/utils";
import { useDashboardStore } from "@/store/dashboard";
import type { OptionLeg } from "@/types/contract";

const FIELDS = [
  { key: "ltp", label: "LTP" },
  { key: "oi", label: "OI" },
  { key: "chg_oi", label: "Chg OI" },
  { key: "iv", label: "IV" },
  { key: "volume", label: "Volume" },
];

const LEG_OPTIONS: { key: OptionLeg; label: string }[] = [
  { key: "CE", label: "Call" },
  { key: "PE", label: "Put" },
];

function Segmented<T extends string>({
  options,
  value,
  onChange,
}: {
  options: { key: T; label: string }[];
  value: T;
  onChange: (value: T) => void;
}) {
  return (
    <div className="flex rounded-md border p-0.5">
      {options.map((option) => (
        <button
          key={option.key}
          type="button"
          onClick={() => onChange(option.key)}
          className={cn(
            "rounded px-2.5 py-1 text-xs font-medium transition-colors",
            value === option.key ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:text-foreground",
          )}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}

/** Feature II: per-strike price / OI / IV history over the session. */
export function HistoryPanel({ expiry }: { expiry?: string }) {
  const { data: chain } = useChain(expiry);
  const selectedStrike = useDashboardStore((state) => state.selectedStrike);
  const setSelectedStrike = useDashboardStore((state) => state.setSelectedStrike);

  const [leg, setLeg] = useState<OptionLeg>("CE");
  const [field, setField] = useState("ltp");

  const strikes = chain?.rows.map((row) => row.strikePrice) ?? [];
  const strike = selectedStrike ?? chain?.atm;
  const query = strike && expiry ? { expiry, strike, leg, field } : null;
  const { data: history } = useHistory(query);

  return (
    <Card>
      <CardHeader className="gap-3">
        <CardTitle>
          Strike History{strike ? ` · ${strike} ${leg}` : ""}
        </CardTitle>
        <div className="flex flex-wrap items-center gap-2">
          <Select
            value={strike ? String(strike) : undefined}
            onValueChange={(value) => setSelectedStrike(Number(value))}
          >
            <SelectTrigger className="w-32 font-mono">
              <SelectValue placeholder="Strike" />
            </SelectTrigger>
            <SelectContent>
              {strikes.map((value) => (
                <SelectItem key={value} value={String(value)} className="font-mono">
                  {value}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          <Segmented options={LEG_OPTIONS} value={leg} onChange={setLeg} />
          <Segmented options={FIELDS} value={field} onChange={setField} />
        </div>
      </CardHeader>
      <CardContent>
        {history ? <StrikeHistoryChart history={history} /> : <div className="h-64" />}
      </CardContent>
    </Card>
  );
}
