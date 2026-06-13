/**
 * Client-only UI state (Zustand).
 *
 * Server state (chain / analytics / history) lives in TanStack Query; this
 * store only holds view selections, the download selection and the
 * in-progress strategy legs.
 */

import { create } from "zustand";

import type { StrategyLeg } from "@/types/contract";

export type DashboardTab = "chain" | "history" | "builder" | "suggestions";

export type HeatMetric = "pchangeinOpenInterest" | "openInterest" | "totalTradedVolume";

interface DashboardState {
  symbol: string;
  expiry?: string;
  tab: DashboardTab;
  selectedStrike?: number;
  heatMetric: HeatMetric;
  builderLegs: StrategyLeg[];
  selectedSymbols: string[];

  setSymbol: (symbol: string) => void;
  setExpiry: (expiry: string) => void;
  setTab: (tab: DashboardTab) => void;
  setSelectedStrike: (strike: number | undefined) => void;
  setHeatMetric: (metric: HeatMetric) => void;
  toggleSymbol: (symbol: string) => void;
  setSelectedSymbols: (symbols: string[]) => void;

  addLeg: (leg: StrategyLeg) => void;
  updateLeg: (index: number, patch: Partial<StrategyLeg>) => void;
  removeLeg: (index: number) => void;
  clearLegs: () => void;
  loadLegs: (legs: StrategyLeg[]) => void;
}

export const useDashboardStore = create<DashboardState>((set) => ({
  symbol: "NIFTY",
  expiry: undefined,
  tab: "chain",
  selectedStrike: undefined,
  heatMetric: "pchangeinOpenInterest",
  builderLegs: [],
  selectedSymbols: [],

  setSymbol: (symbol) => set({ symbol }),
  setExpiry: (expiry) => set({ expiry }),
  setTab: (tab) => set({ tab }),
  setSelectedStrike: (selectedStrike) => set({ selectedStrike }),
  setHeatMetric: (heatMetric) => set({ heatMetric }),
  toggleSymbol: (symbol) =>
    set((state) => ({
      selectedSymbols: state.selectedSymbols.includes(symbol)
        ? state.selectedSymbols.filter((value) => value !== symbol)
        : [...state.selectedSymbols, symbol],
    })),
  setSelectedSymbols: (selectedSymbols) => set({ selectedSymbols }),

  addLeg: (leg) => set((state) => ({ builderLegs: [...state.builderLegs, leg] })),
  updateLeg: (index, patch) =>
    set((state) => ({
      builderLegs: state.builderLegs.map((leg, i) => (i === index ? { ...leg, ...patch } : leg)),
    })),
  removeLeg: (index) =>
    set((state) => ({ builderLegs: state.builderLegs.filter((_, i) => i !== index) })),
  clearLegs: () => set({ builderLegs: [] }),
  loadLegs: (builderLegs) => set({ builderLegs, tab: "builder" }),
}));
