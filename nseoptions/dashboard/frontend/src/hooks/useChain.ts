import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";

/**
 * Read the option chain for an expiry. Seeded via REST and then kept live
 * by the WebSocket (which writes the same ["chain", expiry] cache key).
 */
export function useChain(expiry?: string) {
  return useQuery({
    queryKey: ["chain", expiry],
    queryFn: () => api.chain(expiry),
    enabled: Boolean(expiry),
    refetchInterval: 60_000,
  });
}
