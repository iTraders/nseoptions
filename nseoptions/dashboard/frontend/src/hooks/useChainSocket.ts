import { useEffect, useRef, useState } from "react";

import { useQueryClient } from "@tanstack/react-query";

import { ReconnectingSocket, type ConnectionState } from "@/lib/ws";
import type { ChainOut, SocketMessage } from "@/types/contract";

export interface ChainConnection {
  state: ConnectionState;
  feed: string;
}

/**
 * Open the single live WebSocket and write each snapshot/tick into the
 * TanStack Query cache (keyed by expiry), so any component can read the
 * chain via `useQuery(["chain", expiry])`. Switching expiry re-subscribes
 * without reconnecting and without hitting NSE.
 */
export function useChainSocket(expiry?: string): ChainConnection {
  const queryClient = useQueryClient();
  const socketRef = useRef<ReconnectingSocket | null>(null);
  const [state, setState] = useState<ConnectionState>("connecting");
  const [feed, setFeed] = useState<string>("starting");

  useEffect(() => {
    const socket = new ReconnectingSocket(
      "/ws",
      (message: SocketMessage) => {
        if ((message.type === "snapshot" || message.type === "tick") && message.chain) {
          const chain = message.chain;
          queryClient.setQueryData<ChainOut>(["chain", chain.expiry], chain);
          setFeed("live");
        } else if (message.type === "status" && message.state) {
          setFeed(message.state);
        }
      },
      setState,
    );
    socket.connect();
    socketRef.current = socket;
    return () => socket.close();
  }, [queryClient]);

  useEffect(() => {
    if (expiry && state === "open") {
      socketRef.current?.subscribe(expiry);
    }
  }, [expiry, state]);

  return { state, feed };
}
