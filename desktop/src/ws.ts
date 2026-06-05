import type { BobbyEvent } from './types';

type Handler = (event: BobbyEvent) => void;

export class BobbyWS {
  private ws: WebSocket | null = null;
  private handlers: Handler[] = [];
  private retryDelay = 1000;
  private readonly maxDelay = 30000;
  private alive = true;
  private retryTimer: ReturnType<typeof setTimeout> | null = null;

  constructor(private readonly url: string) {
    this.connect();
  }

  private connect() {
    if (!this.alive) return;

    this.ws = new WebSocket(this.url);

    this.ws.onopen = () => {
      this.retryDelay = 1000;
    };

    this.ws.onmessage = (e: MessageEvent) => {
      try {
        const event = JSON.parse(e.data as string) as BobbyEvent;
        this.handlers.forEach(h => h(event));
      } catch {
        // malformed frame — ignore
      }
    };

    this.ws.onclose = () => {
      if (this.alive) {
        this.retryTimer = setTimeout(() => this.connect(), this.retryDelay);
        this.retryDelay = Math.min(this.retryDelay * 2, this.maxDelay);
      }
    };

    this.ws.onerror = () => {
      this.ws?.close();
    };
  }

  /** Subscribe to Bobby events. Returns an unsubscribe function. */
  onEvent(handler: Handler): () => void {
    this.handlers.push(handler);
    return () => {
      this.handlers = this.handlers.filter(h => h !== handler);
    };
  }

  disconnect() {
    this.alive = false;
    if (this.retryTimer !== null) clearTimeout(this.retryTimer);
    this.ws?.close();
  }
}
