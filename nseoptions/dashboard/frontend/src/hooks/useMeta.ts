import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";

/** Poll dashboard metadata (expiries, status, strike multiple). */
export function useMeta() {
  return useQuery({
    queryKey: ["meta"],
    queryFn: api.meta,
    refetchInterval: 30_000,
  });
}
