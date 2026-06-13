import { keepPreviousData, useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { PayoffIn } from "@/types/contract";

/** Compute the strategy payoff; keeps the previous curve while recomputing. */
export function usePayoff(input: PayoffIn | null) {
  return useQuery({
    queryKey: ["payoff", input],
    queryFn: () => api.payoff(input!),
    enabled: Boolean(input && input.legs.length > 0),
    placeholderData: keepPreviousData,
  });
}
