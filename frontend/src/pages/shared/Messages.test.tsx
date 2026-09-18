import { afterEach, beforeEach, describe, expect, it, vi, type Mock } from "vitest";
import { render, screen, act, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import Messages from "./Messages";
import { AuthProvider } from "../../auth/AuthContext";
import { FakeWebSocket } from "../../test/setup";
import { TOKEN_KEYS } from "../../api/client";

/* ------------------------------------------------------------------------- *
 * Harness: render Messages inside the real AuthProvider (tokens come from
 * localStorage) with the communication API mocked at the module boundary and
 * the refresh helpers from client.ts replaced by controllable mocks (the
 * real tokenStore stays intact via importOriginal). Fake timers drive every
 * timer in the socket state machine deterministically; async steps are
 * flushed with act() + timer advancement rather than waitFor, which deadlocks
 * under fake timers.
 * ------------------------------------------------------------------------- */

vi.mock("../../api/communication", () => ({
  listConversations: vi.fn().mockResolvedValue({
    results: [{ id: "conv-1", other_party: "biz@example.com", unread_count: 0 }],
    count: 1,
  }),
  listMessages: vi.fn().mockResolvedValue({
    results: [
      { id: "m-1", body: "hello from biz", sender: "biz@example.com", created_at: "2026-09-18T10:00:00Z", read_at: null },
    ],
    count: 1,
  }),
  sendMessage: vi.fn().mockResolvedValue({ id: "m-2" }),
  markMessageRead: vi.fn().mockResolvedValue({}),
}));

vi.mock("../../api/auth", () => ({
  // AuthProvider calls me() on mount to restore the session; returning the
  // student keeps the component in its authenticated state.
  me: vi.fn().mockResolvedValue({ id: "u-student", email: "student@example.com", role: "student" }),
  login: vi.fn(),
  register: vi.fn(),
  logout: vi.fn(),
}));

vi.mock("../../api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../api/client")>();
  return {
    ...actual,
    refreshIfExpiring: vi.fn().mockResolvedValue(true),
    refreshAccessToken: vi.fn().mockResolvedValue(true),
  };
});

async function flush(cycles = 8): Promise<void> {
  // Interleave microtasks with 1ms timer advances: React Query state updates
  // and the auth-restore promise chain both need several event-loop turns,
  // and advanceTimersByTimeAsync yields more thoroughly than bare awaits.
  await act(async () => {
    for (let i = 0; i < cycles; i++) {
      await Promise.resolve();
      await vi.advanceTimersByTimeAsync(1);
    }
  });
}

function jwtWithExp(expSeconds: number): string {
  const enc = (o: unknown) => btoa(JSON.stringify(o)).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
  return [enc({ alg: "HS256" }), enc({ exp: expSeconds }), "sig"].join(".");
}

function renderMessages() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <MemoryRouter initialEntries={["/messages"]}>
          <Messages />
        </MemoryRouter>
      </AuthProvider>
    </QueryClientProvider>,
  );
}

async function openThread() {
  renderMessages();
  await flush();
  act(() => {
    fireEvent.click(screen.getByText("biz@example.com"));
  });
  await flush();
  expect(FakeWebSocket.last).toBeDefined();
}

beforeEach(async () => {
  vi.useFakeTimers();
  FakeWebSocket.reset();
  localStorage.clear();
  localStorage.setItem(TOKEN_KEYS.access, jwtWithExp(Math.floor(Date.now() / 1000) + 3600));
  localStorage.setItem(TOKEN_KEYS.refresh, "refresh-token");
  const client = await import("../../api/client");
  (client.refreshIfExpiring as Mock).mockReset().mockResolvedValue(true);
  (client.refreshAccessToken as Mock).mockReset().mockResolvedValue(true);
});

afterEach(() => {
  act(() => {
    vi.runOnlyPendingTimers();
  });
  vi.useRealTimers();
  // Re-establish the module-mock defaults that later tests rely on
  // (beforeEach runs again, but assertions inside the same file can also
  // inspect state between tests).
  vi.clearAllMocks();
});

describe("Messages socket state machine", () => {
  it("opens a socket to the right URL and reports live", async () => {
    await openThread();
    const sock = FakeWebSocket.last!;
    expect(sock.url).toContain("/ws/conversations/conv-1/?token=");
    act(() => sock.serverOpen());
    expect(screen.getByText("live")).toBeInTheDocument();
  });

  it("pre-flight refreshes before opening the socket when the token is nearly expired", async () => {
    // refreshIfExpiring never resolves (refresh round-trip in flight):
    // the socket must NOT be opened until it settles.
    const client = await import("../../api/client");
    (client.refreshIfExpiring as Mock).mockReturnValue(new Promise(() => {}));
    renderMessages();
    await flush();
    act(() => {
      fireEvent.click(screen.getByText("biz@example.com"));
    });
    await flush();
    expect(FakeWebSocket.instances).toHaveLength(0);
  });

  it("on 4403 retries once after a forced refresh, then gives up for good", async () => {
    await openThread();
    const first = FakeWebSocket.last!;
    act(() => first.serverOpen());
    expect(screen.getByText("live")).toBeInTheDocument();

    // Server rejects the token with the custom close code → retry scheduled.
    act(() => first.serverClose(4403));
    expect(screen.getByText("reconnecting via polling")).toBeInTheDocument();

    // Refresh resolves; the 250ms retry timer fires a second socket.
    await act(async () => {
      await vi.advanceTimersByTimeAsync(300);
    });
    expect(FakeWebSocket.instances.length).toBe(2);
    const second = FakeWebSocket.last!;

    // Second 4403 → permanent give-up: the 10s heartbeat must stay silent.
    act(() => second.serverClose(4403));
    await act(async () => {
      await vi.advanceTimersByTimeAsync(60_000);
    });
    expect(FakeWebSocket.instances.length).toBe(2);
  });

  it("detects zombie sockets when pings go unanswered and force-closes", async () => {
    await openThread();
    const sock = FakeWebSocket.last!;
    act(() => sock.serverOpen());
    expect(screen.getByText("live")).toBeInTheDocument();

    // First ping at 10s → answered with pong → stays open.
    await act(async () => {
      await vi.advanceTimersByTimeAsync(10_000);
    });
    expect(sock.sent).toContain(JSON.stringify({ type: "ping" }));
    act(() => sock.serverMessage({ type: "pong" }));
    expect(sock.readyState).toBe(FakeWebSocket.OPEN);

    // Second ping goes unanswered → the NEXT tick (t=30s) declares the
    // socket a zombie and force-closes it.
    await act(async () => {
      await vi.advanceTimersByTimeAsync(10_000);
    });
    expect(sock.sent.filter((s) => s === JSON.stringify({ type: "ping" }))).toHaveLength(2);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(10_000); // t=30s: zombie verdict
    });
    expect(sock.readyState).toBe(FakeWebSocket.CLOSED);
  });

  it("heartbeat keeps retrying after fast retries exhaust, reconnecting on its own", async () => {
    await openThread();
    // Exhaust the fast-retry budget: open+close each attempt and advance
    // through the full backoff chain (1.5+3+4.5s). Note opening an attempt
    // resets the retry counter by design, so the last close always
    // schedules one more retry — after this block exactly one is pending.
    for (let i = 1; i <= 3; i++) {
      const s = FakeWebSocket.last!;
      act(() => s.serverOpen());
      act(() => s.serverClose(1006));
      await act(async () => {
        await vi.advanceTimersByTimeAsync(1_500 * i + 10);
      });
    }
    const attemptsAfterBudget = FakeWebSocket.instances.length;
    expect(attemptsAfterBudget).toBe(4);

    // From here every pending timer drains with the socket left CONNECTING;
    // the state machine must keep producing fresh attempts on its own
    // (pending retry + heartbeat ticks) rather than going silent.
    let peak = attemptsAfterBudget;
    for (let step = 0; step < 25; step++) {
      await act(async () => {
        await vi.advanceTimersByTimeAsync(1_000);
      });
      peak = Math.max(peak, FakeWebSocket.instances.length);
      // Keep whichever socket is newest in CONNECTING (never open it) so
      // every scheduled retry/heartbeat fires while the slot is occupied.
    }
    expect(peak).toBeGreaterThan(attemptsAfterBudget);

    // When the backend finally accepts, the status returns to live.
    const revived = FakeWebSocket.last!;
    act(() => revived.serverOpen());
    expect(screen.getByText("live")).toBeInTheDocument();
  });

  it("falls back to REST send when the socket never opens", async () => {
    const { sendMessage } = await import("../../api/communication");
    await openThread();
    const sock = FakeWebSocket.last!;
    // Socket stays CONNECTING (proxy limbo) — the 5s timeout closes it.
    await act(async () => {
      await vi.advanceTimersByTimeAsync(5_100);
    });
    expect(sock.readyState).toBe(FakeWebSocket.CLOSED);

    // The composer still works via REST.
    const input = screen.getByPlaceholderText("Type a message…");
    act(() => {
      fireEvent.change(input, { target: { value: "hello via rest" } });
    });
    act(() => {
      fireEvent.submit(input.closest("form")!);
    });
    await flush(5);
    expect(sendMessage).toHaveBeenCalledWith("conv-1", "hello via rest");
  });
});
