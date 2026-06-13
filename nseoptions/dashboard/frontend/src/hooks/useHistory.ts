import { useQuery } from "@tanstack/react-query";

import { api, type HistoryQuery } from "@/lib/api";

/** Per-strike, per-leg history series for a tracked field (LTP/OI/IV/...). */
export function useHistory(query: HistoryQuery | null) {
  return useQuery({
    queryKey: ["history", query],
    queryFn: () => api.history(query!),
    enabled: Boolean(query?.expiry && query?.strike),
    refetchInterval: 30_000,
  });
}
