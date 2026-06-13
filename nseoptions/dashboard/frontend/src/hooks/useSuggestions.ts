import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";

/** Rules-based strategy suggestions + the market context for an expiry. */
export function useSuggestions(expiry?: string) {
  return useQuery({
    queryKey: ["suggestions", expiry],
    queryFn: () => api.suggestions(expiry),
    enabled: Boolean(expiry),
    refetchInterval: 60_000,
  });
}
