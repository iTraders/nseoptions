/**
 * Typed REST / WebSocket contract.
 *
 * These interfaces mirror the pydantic models in
 * `nseoptions/dashboard/schemas.py` one-to-one. The Python backend is the
 * authoritative, validated source of truth, so the frontend trusts the
 * shape and keeps the live path allocation-free (no per-tick re-parse).
 */

export interface LegQuote {
  openInterest: number;
  changeinOpenInterest: number;
  pchangeinOpenInterest: number;
  totalTradedVolume: number;
  impliedVolatility: number;
  lastPrice: number;
  change: number;
  pChange: number;
  totalBuyQuantity: number;
  totalSellQuantity: number;
  buyQuantity1: number;
  buyPrice1: number;
  sellQuantity1: number;
  sellPrice1: number;
}

export interface StrikeRow {
  strikePrice: number;
  ce: LegQuote | null;
  pe: LegQuote | null;
  is_atm: boolean;
}

export interface Greeks {
  delta: number;
  gamma: number;
  theta: number;
  vega: number;
  rho: number;
  iv_missing: boolean;
}

export interface ChainOut {
  symbol: string;
  expiry: string;
  underlying: number;
  timestamp: string;
  atm: number;
  multiple: number;
  put_call_ratio: number;
  tot_oi_ce: number;
  tot_oi_pe: number;
  tot_vol_ce: number;
  tot_vol_pe: number;
  rows: StrikeRow[];
}

export interface MetaOut {
  symbol: string;
  expiries: string[];
  expiry: string | null;
  multiple: number | null;
  nstrikes: number;
  status: string;
  detail: string | null;
  underlying: number | null;
  timestamp: string | null;
}

export interface HealthOut {
  status: string;
  symbol: string;
  last_poll: string | null;
  clients: number;
}

export interface StrikeLoss {
  strikePrice: number;
  loss: number;
}

export interface WallPoint {
  strikePrice: number;
  openInterest: number;
  changeinOpenInterest: number;
}

export interface IVPoint {
  strikePrice: number;
  ce_iv: number;
  pe_iv: number;
}

export interface AnalyticsOut {
  symbol: string;
  expiry: string;
  underlying: number;
  max_pain: number | null;
  loss_by_strike: StrikeLoss[];
  support: WallPoint[];
  resistance: WallPoint[];
  iv_smile: IVPoint[];
  no_data: boolean;
}

export type OptionLeg = "CE" | "PE";
export type OrderSide = "BUY" | "SELL";

export interface StrategyLeg {
  strike: number;
  leg: OptionLeg;
  side: OrderSide;
  qty: number;
  price?: number | null;
}

export interface PayoffIn {
  symbol: string;
  expiry: string;
  lots: number;
  legs: StrategyLeg[];
}

export interface PayoffPoint {
  spot: number;
  pnl: number;
}

export interface PayoffOut {
  spot: number;
  lot_size: number;
  curve: PayoffPoint[];
  breakevens: number[];
  max_profit: number | null;
  max_loss: number | null;
  net_greeks: Greeks;
  estimated: boolean;
}

export type StrategyBias = "bullish" | "bearish" | "neutral" | "volatile";

export interface Suggestion {
  name: string;
  bias: StrategyBias;
  legs: StrategyLeg[];
  rationale: string[];
  score: number;
  max_profit: number | null;
  max_loss: number | null;
  breakevens: number[];
}

export interface SuggestionsOut {
  symbol: string;
  expiry: string;
  context: Record<string, number | string | null>;
  suggestions: Suggestion[];
}

export interface HistoryPoint {
  ts: string;
  value: number;
}

export interface HistoryOut {
  symbol: string;
  expiry: string;
  strike: number;
  leg: string;
  field: string;
  points: HistoryPoint[];
}

export type SocketMessageType = "snapshot" | "tick" | "status";

export interface SocketMessage {
  type: SocketMessageType;
  chain?: ChainOut | null;
  state?: string | null;
  detail?: string | null;
}
