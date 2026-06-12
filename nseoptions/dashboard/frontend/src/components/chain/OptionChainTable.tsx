import { useMemo } from "react";

import { compact, num, pct, signed } from "@/lib/format";
import { diverging } from "@/lib/heatmap";
import { cn } from "@/lib/utils";
import type { ChainOut, StrikeRow } from "@/types/contract";

import { HeatCell } from "./HeatCell";

interface OptionChainTableProps {
  chain: ChainOut;
  selectedStrike?: number;
  onSelectStrike?: (strike: number) => void;
}

const CALL_HEADERS = ["OI", "Chg OI%", "Vol", "IV", "LTP"];

interface OIBarProps {
  value: number;
  max: number;
  side: "call" | "put";
  align: "left" | "right";
}

/** Open-interest magnitude bar (Sensibull-style), tinted by leg side. */
function OIBar({ value, max, side, align }: OIBarProps) {
  const width = max > 0 ? Math.min(100, (value / max) * 100) : 0;
  return (
    <div className={cn("relative px-2 py-1 tabular-nums", align === "right" ? "text-right" : "text-left")}>
      <div
        className={cn(
          "absolute inset-y-0",
          align === "right" ? "right-0" : "left-0",
          side === "call" ? "bg-call/25" : "bg-put/25",
        )}
        style={{ width: `${width}%` }}
      />
      <span className="relative">{compact(value)}</span>
    </div>
  );
}

interface RowProps {
  row: StrikeRow;
  underlying: number;
  maxOI: number;
  boundChg: number;
  selected: boolean;
  onSelect?: (strike: number) => void;
}

function Row({ row, underlying, maxOI, boundChg, selected, onSelect }: RowProps) {
  const callItm = row.strikePrice < underlying; // ITM calls on the left
  const putItm = row.strikePrice > underlying; // ITM puts on the right

  const change = (value?: number | null) =>
    cn("text-[10px]", (value ?? 0) >= 0 ? "text-profit" : "text-loss");

  return (
    <tr
      className={cn(
        "cursor-pointer border-b border-border/40 transition-colors hover:bg-accent/40",
        row.is_atm && "bg-atm/10 font-medium",
        selected && "ring-1 ring-inset ring-primary",
      )}
      onClick={() => onSelect?.(row.strikePrice)}
    >
      {/* ---- CALL side (right-aligned, hugging the strike) ---- */}
      <td className={cn(callItm && "bg-call/[0.06]")}>
        <OIBar value={row.ce?.openInterest ?? 0} max={maxOI} side="call" align="right" />
      </td>
      <td>
        <HeatCell t={diverging(row.ce?.pchangeinOpenInterest ?? 0, boundChg)} active={Boolean(row.ce)}>
          {signed(row.ce?.pchangeinOpenInterest ?? null)}
        </HeatCell>
      </td>
      <td className={cn("px-2 py-1 text-right tabular-nums text-muted-foreground", callItm && "bg-call/[0.06]")}>
        {compact(row.ce?.totalTradedVolume)}
      </td>
      <td className={cn("px-2 py-1 text-right tabular-nums", callItm && "bg-call/[0.06]")}>
        {num(row.ce?.impliedVolatility)}
      </td>
      <td className={cn("px-2 py-1 text-right tabular-nums", callItm && "bg-call/[0.06]")}>
        <div>{num(row.ce?.lastPrice)}</div>
        <div className={change(row.ce?.pChange)}>{pct(row.ce?.pChange ?? null)}</div>
      </td>

      {/* ---- STRIKE (centre) ---- */}
      <td
        className={cn(
          "border-x bg-muted/40 px-3 py-1 text-center font-mono font-semibold tabular-nums",
          row.is_atm && "bg-atm/25 text-atm",
        )}
      >
        {num(row.strikePrice, 0)}
      </td>

      {/* ---- PUT side (left-aligned, mirrored) ---- */}
      <td className={cn("px-2 py-1 text-left tabular-nums", putItm && "bg-put/[0.06]")}>
        <div>{num(row.pe?.lastPrice)}</div>
        <div className={change(row.pe?.pChange)}>{pct(row.pe?.pChange ?? null)}</div>
      </td>
      <td className={cn("px-2 py-1 text-left tabular-nums", putItm && "bg-put/[0.06]")}>
        {num(row.pe?.impliedVolatility)}
      </td>
      <td className={cn("px-2 py-1 text-left tabular-nums text-muted-foreground", putItm && "bg-put/[0.06]")}>
        {compact(row.pe?.totalTradedVolume)}
      </td>
      <td>
        <HeatCell
          t={diverging(row.pe?.pchangeinOpenInterest ?? 0, boundChg)}
          active={Boolean(row.pe)}
          className="text-left"
        >
          {signed(row.pe?.pchangeinOpenInterest ?? null)}
        </HeatCell>
      </td>
      <td className={cn(putItm && "bg-put/[0.06]")}>
        <OIBar value={row.pe?.openInterest ?? 0} max={maxOI} side="put" align="left" />
      </td>
    </tr>
  );
}

/**
 * The live option chain: CALLS (left) | STRIKE (centre) | PUTS (right,
 * mirrored), mirroring the Excel template with a sticky header, ATM-row
 * highlight, ITM shading and the diverging %-change-in-OI heat cells.
 */
export function OptionChainTable({ chain, selectedStrike, onSelectStrike }: OptionChainTableProps) {
  const { maxOI, boundChg } = useMemo(() => {
    let oi = 1;
    let chg = 1;
    for (const row of chain.rows) {
      for (const quote of [row.ce, row.pe]) {
        if (!quote) continue;
        oi = Math.max(oi, quote.openInterest);
        chg = Math.max(chg, Math.abs(quote.pchangeinOpenInterest));
      }
    }
    return { maxOI: oi, boundChg: chg };
  }, [chain.rows]);

  return (
    <div className="max-h-[calc(100vh-13rem)] overflow-auto rounded-lg border">
      <table className="w-full border-collapse text-xs">
        <thead className="sticky top-0 z-10 bg-card shadow-sm">
          <tr className="text-[11px] uppercase tracking-wide">
            <th colSpan={5} className="border-b bg-call/10 py-1.5 text-center font-semibold text-call">
              Calls
            </th>
            <th className="border-b py-1.5 text-center font-semibold">Strike</th>
            <th colSpan={5} className="border-b bg-put/10 py-1.5 text-center font-semibold text-put">
              Puts
            </th>
          </tr>
          <tr className="border-b text-[11px] text-muted-foreground">
            {CALL_HEADERS.map((header) => (
              <th key={`c-${header}`} className="px-2 py-1 text-right font-medium">
                {header}
              </th>
            ))}
            <th className="px-2 py-1 text-center font-medium">Price</th>
            {[...CALL_HEADERS].reverse().map((header) => (
              <th key={`p-${header}`} className="px-2 py-1 text-left font-medium">
                {header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {chain.rows.map((row) => (
            <Row
              key={row.strikePrice}
              row={row}
              underlying={chain.underlying}
              maxOI={maxOI}
              boundChg={boundChg}
              selected={selectedStrike === row.strikePrice}
              onSelect={onSelectStrike}
            />
          ))}
        </tbody>
      </table>
    </div>
  );
}
