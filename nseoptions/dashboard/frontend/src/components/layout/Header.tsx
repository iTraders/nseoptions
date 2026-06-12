import { Activity } from "lucide-react";

import { ThemeToggle } from "@/components/ThemeToggle";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import type { ChainConnection } from "@/hooks/useChainSocket";
import { inr } from "@/lib/format";
import { useDashboardStore } from "@/store/dashboard";
import type { MetaOut } from "@/types/contract";

import { StatusBadge } from "./StatusBadge";

interface HeaderProps {
  meta?: MetaOut;
  connection: ChainConnection;
}

/** Sticky top bar: brand, symbol, spot, expiry selector and feed status. */
export function Header({ meta, connection }: HeaderProps) {
  const { symbol, expiry, setExpiry } = useDashboardStore();

  const expiries = meta?.expiries ?? [];
  const current = expiry ?? meta?.expiry ?? undefined;

  return (
    <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b bg-background/80 px-4 backdrop-blur">
      <div className="flex items-center gap-2 text-sm font-semibold tracking-tight">
        <Activity className="h-5 w-5 text-primary" />
        NSE Options
      </div>

      <Separator orientation="vertical" className="h-6" />

      <Badge variant="secondary" className="font-mono">
        {symbol}
      </Badge>
      {meta?.underlying ? (
        <span className="font-mono text-sm text-muted-foreground">{inr(meta.underlying)}</span>
      ) : null}

      <div className="ml-auto flex items-center gap-3">
        {expiries.length > 0 ? (
          <Select value={current} onValueChange={setExpiry}>
            <SelectTrigger className="h-8 w-[160px] font-mono text-xs">
              <SelectValue placeholder="Expiry" />
            </SelectTrigger>
            <SelectContent>
              {expiries.map((value) => (
                <SelectItem key={value} value={value} className="font-mono text-xs">
                  {value}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        ) : null}

        <StatusBadge {...connection} />
        <ThemeToggle />
      </div>
    </header>
  );
}
