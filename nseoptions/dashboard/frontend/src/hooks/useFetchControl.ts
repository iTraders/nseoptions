import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { FetchStatus } from "@/types/contract";

const STATUS_KEY = ["fetch-status"];

/**
 * Poll the downloader status and expose start/stop mutations.
 *
 * Both mutations return the fresh FetchStatus, which is written straight
 * into the query cache so the controls reflect the new state immediately
 * without waiting for the next poll.
 */
export function useFetchControl() {
  const queryClient = useQueryClient();

  const status = useQuery({
    queryKey: STATUS_KEY,
    queryFn: api.fetchStatus,
    refetchInterval: 5_000,
  });

  const start = useMutation({
    mutationFn: (symbols: string[]) => api.fetchStart(symbols),
    onSuccess: (data: FetchStatus) => queryClient.setQueryData(STATUS_KEY, data),
  });

  const stop = useMutation({
    mutationFn: api.fetchStop,
    onSuccess: (data: FetchStatus) => queryClient.setQueryData(STATUS_KEY, data),
  });

  return { status, start, stop };
}
