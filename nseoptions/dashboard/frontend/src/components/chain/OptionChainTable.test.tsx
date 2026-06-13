import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { ChainOut, LegQuote } from "@/types/contract";

import { OptionChainTable } from "./OptionChainTable";

function quote(overrides: Partial<LegQuote> = {}): LegQuote {
  return {
    openInterest: 100000,
    changeinOpenInterest: 0,
    pchangeinOpenInterest: 0,
    totalTradedVolume: 5000,
    impliedVolatility: 12,
    lastPrice: 50,
    change: 0,
    pChange: 0,
    totalBuyQuantity: 0,
    totalSellQuantity: 0,
    buyQuantity1: 0,
    buyPrice1: 0,
    sellQuantity1: 0,
    sellPrice1: 0,
    ...overrides,
  };
}

const chain: ChainOut = {
  symbol: "NIFTY",
  expiry: "26-Jun-2025",
  underlying: 23456.75,
  timestamp: "2025-06-13T15:30:00",
  atm: 23450,
  multiple: 50,
  put_call_ratio: 1.2,
  tot_oi_ce: 1,
  tot_oi_pe: 1,
  tot_vol_ce: 1,
  tot_vol_pe: 1,
  rows: [
    { strikePrice: 23400, ce: quote({ pchangeinOpenInterest: 10 }), pe: quote({ pchangeinOpenInterest: -5 }), is_atm: false },
    { strikePrice: 23450, ce: quote(), pe: quote(), is_atm: true },
    { strikePrice: 23500, ce: quote(), pe: quote(), is_atm: false },
  ],
};

describe("OptionChainTable", () => {
  it("renders the mirrored CALL | STRIKE | PUT layout", () => {
    render(<OptionChainTable chain={chain} />);
    expect(screen.getByText("Calls")).toBeInTheDocument();
    expect(screen.getByText("Puts")).toBeInTheDocument();
    expect(screen.getByText("Strike")).toBeInTheDocument();
    expect(screen.getByText("23,450")).toBeInTheDocument();
  });

  it("flags the ATM strike row with the atm token", () => {
    render(<OptionChainTable chain={chain} />);
    const atmCell = screen.getByText("23,450");
    expect(atmCell.className).toContain("text-atm");
  });
});
