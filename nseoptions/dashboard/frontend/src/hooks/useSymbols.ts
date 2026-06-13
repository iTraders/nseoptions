import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";

/** Fetch the selectable download symbol catalogue (rarely changes). */
export function useSymbols() {
  return useQuery({
    queryKey: ["symbols"],
    queryFn: api.symbols,
    staleTime: Infinity,
  });
}
