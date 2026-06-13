/** Typed REST client for the dashboard backend. */

import type {
  AnalyticsOut,
  ChainOut,
  FetchStatus,
  HealthOut,
  HistoryOut,
  MetaOut,
  PayoffIn,
  PayoffOut,
  SuggestionsOut,
  SymbolsOut,
} from "@/types/contract";

// Empty base => origin-relative paths: works behind the Vite dev proxy and
// in production where the backend serves the SPA from the same origin.
const BASE = (import.meta.env.VITE_API_BASE as string | undefined) ?? "";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

type QueryParams = Record<string, string | number | undefined | null>;

function queryString(params?: QueryParams): string {
  if (!params) return "";
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") {
      search.set(key, String(value));
    }
  }
  const encoded = search.toString();
  return encoded ? `?${encoded}` : "";
}

async function unwrap<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      detail = body?.detail ?? detail;
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(response.status, detail);
  }
  return (await response.json()) as T;
}

async function getJSON<T>(path: string, params?: QueryParams): Promise<T> {
  const response = await fetch(`${BASE}${path}${queryString(params)}`);
  return unwrap<T>(response);
}

async function postJSON<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return unwrap<T>(response);
}

export interface HistoryQuery {
  expiry: string;
  strike: number;
  leg: string;
  field: string;
  since?: string;
}

export const api = {
  health: () => getJSON<HealthOut>("/api/health"),
  meta: () => getJSON<MetaOut>("/api/meta"),
  chain: (expiry?: string) => getJSON<ChainOut>("/api/chain", { expiry }),
  analytics: (expiry?: string) => getJSON<AnalyticsOut>("/api/analytics", { expiry }),
  suggestions: (expiry?: string) => getJSON<SuggestionsOut>("/api/suggestions", { expiry }),
  history: (query: HistoryQuery) => getJSON<HistoryOut>("/api/history", { ...query }),
  payoff: (body: PayoffIn) => postJSON<PayoffOut>("/api/strategy/payoff", body),

  symbols: () => getJSON<SymbolsOut>("/api/symbols"),
  fetchStatus: () => getJSON<FetchStatus>("/api/fetch/status"),
  fetchStart: (symbols: string[]) => postJSON<FetchStatus>("/api/fetch/start", { symbols }),
  fetchStop: () => postJSON<FetchStatus>("/api/fetch/stop", {}),
};
