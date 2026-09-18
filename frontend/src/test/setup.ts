import "@testing-library/jest-dom/vitest";

// jsdom does not implement scrollIntoView; the thread auto-scroll calls it.
Element.prototype.scrollIntoView = () => {};

/**
 * Minimal fake WebSocket for the chat socket tests. Records every instance
 * so a test can drive the connection through open/message/close/error and
 * assert on what the component sent. `readyState` is mutable so tests can
 * stage the CONNECTING limbo (a proxy that never completes the handshake).
 */
class FakeWebSocket {
  static readonly CONNECTING = 0;
  static readonly OPEN = 1;
  static readonly CLOSING = 2;
  static readonly CLOSED = 3;
  readonly CONNECTING = FakeWebSocket.CONNECTING;
  readonly OPEN = FakeWebSocket.OPEN;
  readonly CLOSING = FakeWebSocket.CLOSING;
  readonly CLOSED = FakeWebSocket.CLOSED;

  static instances: FakeWebSocket[] = [];

  /** Most recent socket instance (a real getter — Object.assign would copy
   * the computed value once, freezing it at undefined forever). */
  static get last(): FakeWebSocket | undefined {
    return FakeWebSocket.instances[FakeWebSocket.instances.length - 1];
  }

  static reset() {
    FakeWebSocket.instances = [];
  }

  url: string;
  readyState = FakeWebSocket.CONNECTING;
  sent: string[] = [];
  onopen: (() => void) | null = null;
  onmessage: ((event: { data: string }) => void) | null = null;
  onclose: ((event: { code: number }) => void) | null = null;
  onerror: (() => void) | null = null;

  constructor(url: string | URL) {
    this.url = String(url);
    FakeWebSocket.instances.push(this);
  }

  send(data: string) {
    this.sent.push(data);
  }

  close(code = 1006) {
    if (this.readyState >= FakeWebSocket.CLOSING) return;
    this.readyState = FakeWebSocket.CLOSED;
    // A real close() always delivers a close event to the page's handler —
    // including the component's own CONNECTING-timeout close. Without this,
    // the state machine never learned its own timeout fired.
    queueMicrotask(() => this.onclose?.({ code }));
  }

  // --- test controls -------------------------------------------------------
  serverOpen() {
    this.readyState = FakeWebSocket.OPEN;
    this.onopen?.();
  }

  serverMessage(payload: unknown) {
    this.onmessage?.({ data: JSON.stringify(payload) });
  }

  serverClose(code: number) {
    this.readyState = FakeWebSocket.CLOSED;
    this.onclose?.({ code });
  }
}

// @ts-expect-error — installed as the global the component under test uses
window.WebSocket = FakeWebSocket;

export { FakeWebSocket };
