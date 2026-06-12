import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";

/** Derived analytics (max-pain, OI walls, IV smile) for an expiry. */
export function useAnalytics(expiry?: string) {
  return useQuery({
    queryKey: ["analytics", expiry],
    queryFn: () => api.analytics(expiry),
    enabled: Boolean(expiry),
    refetchInterval: 60_000,
  });
}
