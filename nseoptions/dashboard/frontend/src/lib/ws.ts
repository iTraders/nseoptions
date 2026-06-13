/**
 * Reconnecting WebSocket client for the live option chain feed.
 *
 * Emits parsed `SocketMessage`s to a handler, auto-reconnects with capped
 * exponential backoff, and sends a periodic heartbeat. A single instance is
 * shared by the app (one socket, many subscribers via the query cache).
 */

import type { SocketMessage } from "@/types/contract";

export type ConnectionState = "connecting" | "open" | "closed";

type MessageHandler = (message: SocketMessage) => void;
type StateHandler = (state: ConnectionState) => void;

const MAX_BACKOFF_MS = 15_000;
const HEARTBEAT_MS = 20_000;

function socketUrl(path: string): string {
  const base = import.meta.env.VITE_API_BASE as string | undefined;
  if (base && /^https?:\/\//.test(base)) {
    return base.replace(/^http/, "ws") + path;
  }
  const protocol = window.location.protocol === "https:" ? "wss" : "ws";
  return `${protocol}://${window.location.host}${path}`;
}

export class ReconnectingSocket {
  private socket?: WebSocket;
  private attempt = 0;
  private stopped = false;
  private heartbeat?: ReturnType<typeof setInterval>;
  private reconnectTimer?: ReturnType<typeof setTimeout>;

  constructor(
    private path: string,
    private onMessage: MessageHandler,
    private onState?: StateHandler,
  ) {}

  connect(): void {
    this.stopped = false;
    this.open();
  }

  private open(): void {
    this.onState?.("connecting");
    const socket = new WebSocket(socketUrl(this.path));
    this.socket = socket;

    socket.onopen = () => {
      this.attempt = 0;
      this.onState?.("open");
      this.heartbeat = setInterval(() => this.send({ type: "ping" }), HEARTBEAT_MS);
    };

    socket.onmessage = (event) => {
      try {
        this.onMessage(JSON.parse(event.data) as SocketMessage);
      } catch {
        /* ignore malformed frames */
      }
    };

    socket.onclose = () => {
      this.clearHeartbeat();
      this.onState?.("closed");
      if (!this.stopped) this.scheduleReconnect();
    };

    socket.onerror = () => socket.close();
  }

  private scheduleReconnect(): void {
    const delay = Math.min(1000 * 2 ** this.attempt, MAX_BACKOFF_MS);
    this.attempt += 1;
    this.reconnectTimer = setTimeout(() => this.open(), delay);
  }

  private clearHeartbeat(): void {
    if (this.heartbeat) clearInterval(this.heartbeat);
    this.heartbeat = undefined;
  }

  /** Send a JSON message if the socket is open (used for subscribe/ping). */
  send(payload: Record<string, unknown>): void {
    if (this.socket?.readyState === WebSocket.OPEN) {
      this.socket.send(JSON.stringify(payload));
    }
  }

  /** Switch the subscribed expiry without reconnecting (pure cache read). */
  subscribe(expiry: string): void {
    this.send({ type: "subscribe", expiry });
  }

  close(): void {
    this.stopped = true;
    this.clearHeartbeat();
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    this.socket?.close();
  }
}
