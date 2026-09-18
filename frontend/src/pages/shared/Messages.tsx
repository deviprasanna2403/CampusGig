import { useCallback, useEffect, useRef, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  listConversations,
  listMessages,
  markMessageRead,
  sendMessage,
} from "../../api/communication";
import { tokenStore, refreshIfExpiring, refreshAccessToken } from "../../api/client";
import { useAuth } from "../../auth/AuthContext";
import ErrorState from "../../components/ErrorState";

/**
 * Two-pane messaging with real-time delivery over the Phase 7 Channels
 * consumer (F6): `ws://…/ws/conversations/<id>/?token=<JWT access>`.
 *
 * Protocol (apps/communication/consumers.py):
 * - in:  {id, body, sender_id, created_at} per new message, or {error: "..."}
 * - out: {body: "..."} — the consumer persists and broadcasts to the group
 * - close 4403 when unauthorized / not a participant
 *
 * The WS is a wake-up signal: incoming events invalidate the React Query
 * cache so the REST endpoints (single source of truth for shapes, sender
 * email, read receipts) refetch immediately. When the socket is down the
 * page falls back to the previous 5s/10s REST polling and REST sending, so
 * chat degrades gracefully instead of breaking.
 *
 * Long-lived tabs: each connect pre-flights the access token (refreshing via
 * the shared single-flight path when missing/nearly expired), and a 4403
 * close triggers one refresh-authenticated retry before giving up — so an
 * expired JWT re-authenticates instead of silently degrading to polling.
 */
type WsStatus = "connecting" | "open" | "down";

export default function Messages() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [activeId, setActiveId] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [wsStatus, setWsStatus] = useState<WsStatus>("down");
  const bottomRef = useRef<HTMLDivElement>(null);
  const socketRef = useRef<WebSocket | null>(null);
  const mountedRef = useRef(true);
  const activeIdRef = useRef<string | null>(null);
  const retryRef = useRef(0);
  const retriedAfterAuth = useRef(false);

  activeIdRef.current = activeId;

  const convsQ = useQuery({
    queryKey: ["conversations"],
    queryFn: listConversations,
    refetchInterval: wsStatus === "open" ? false : 10_000,
  });

  const msgsQ = useQuery({
    queryKey: ["messages", activeId],
    queryFn: () => listMessages(activeId!),
    enabled: !!activeId,
    refetchInterval: wsStatus === "open" ? false : 5_000,
  });

  const refreshThread = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ["messages", activeIdRef.current] });
    queryClient.invalidateQueries({ queryKey: ["conversations"] });
  }, [queryClient]);

  // --- WebSocket lifecycle -------------------------------------------------
  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  useEffect(() => {
    if (!activeId || !user) {
      setWsStatus("down");
      return;
    }
    let socket: WebSocket | null = null;
    let retryTimer: number | undefined;
    let gaveUp = false;
    retriedAfterAuth.current = false;

    const connect = () => {
      // Reconnects reuse this closure, so always take a fresh token: the
      // stored access may have expired while we were disconnected. SimpleJWT
      // access tokens are short-lived; refresh (single-flight, shared with
      // the axios layer) when missing or nearly expired.
      void refreshIfExpiring().then((ok) => {
        if (!ok || !mountedRef.current || activeIdRef.current !== activeId) return;
        openSocket();
      });
    };

    const openSocket = () => {
      const token = tokenStore.access;
      if (!token || !mountedRef.current || activeIdRef.current !== activeId) return;
      const proto = window.location.protocol === "https:" ? "wss" : "ws";
      socket = new WebSocket(
        `${proto}://${window.location.host}/ws/conversations/${activeId}/?token=${encodeURIComponent(token)}`,
      );
      socketRef.current = socket;
      setWsStatus("connecting");

      socket.onopen = () => {
        if (!mountedRef.current) return;
        retryRef.current = 0;
        setWsStatus("open");
        // Catch anything missed while we were disconnected.
        refreshThread();
      };
      socket.onmessage = (event) => {
        if (!mountedRef.current) return;
        try {
          const data = JSON.parse(event.data) as { error?: string; id?: string };
          if (data.error) {
            setError(data.error);
            return;
          }
          // A new message (from anyone, incl. our own sends) → refetch.
          setError(null);
          refreshThread();
        } catch {
          // Ignore malformed frames; the REST poll remains authoritative.
        }
      };
      socket.onclose = (event) => {
        socketRef.current = null;
        if (!mountedRef.current || gaveUp || activeIdRef.current !== activeId) return;
        setWsStatus("down");
        // 4403 = unauthorized. Most commonly a token that expired between
        // connects (long-lived tab): force one refresh-authenticated retry
        // before treating it as a real "not a participant" rejection.
        if (event.code === 4403) {
          if (retriedAfterAuth.current) {
            gaveUp = true;
            return;
          }
          retriedAfterAuth.current = true;
          void refreshAccessToken().then((ok) => {
            if (ok && mountedRef.current && activeIdRef.current === activeId) {
              retryTimer = window.setTimeout(openSocket, 250);
            } else {
              gaveUp = true;
            }
          });
          return;
        }
        if (retryRef.current >= 3) {
          gaveUp = true;
          return;
        }
        retryRef.current += 1;
        retryTimer = window.setTimeout(connect, 1500 * retryRef.current);
      };
    };

    connect();

    return () => {
      gaveUp = true;
      if (retryTimer) window.clearTimeout(retryTimer);
      if (socket && socket.readyState <= WebSocket.OPEN) {
        socket.onclose = null; // intentional close — no reconnect, no state churn
        socket.close();
      }
      socketRef.current = null;
    };
  }, [activeId, user, refreshThread]);

  const sendM = useMutation({
    mutationFn: () => sendMessage(activeId!, draft.trim()),
    onSuccess: () => {
      setDraft("");
      setError(null);
      refreshThread();
    },
    onError: (err) => setError(err instanceof Error ? err.message : "Could not send."),
  });

  const sendOverWs = useCallback((): boolean => {
    const socket = socketRef.current;
    const text = draft.trim();
    if (wsStatus !== "open" || !socket || socket.readyState !== WebSocket.OPEN || !text) {
      return false;
    }
    socket.send(JSON.stringify({ body: text }));
    setDraft("");
    setError(null);
    // Our own broadcast comes back through onmessage → refetch.
    return true;
  }, [draft, wsStatus]);

  const readM = useMutation({
    mutationFn: markMessageRead,
    onSuccess: () => refreshThread(),
  });

  const messages = msgsQ.data?.results ?? [];

  // Mark incoming unread messages as read while the thread is open.
  useEffect(() => {
    if (!user) return;
    for (const m of messages) {
      if (!m.read_at && m.sender !== user.email) {
        readM.mutate(m.id);
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [msgsQ.data, user]);

  // Keep the thread scrolled to the newest message.
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length]);

  const activeConv = convsQ.data?.results.find((c) => c.id === activeId);

  return (
    <section className="messages-layout">
      <aside className="card conv-list">
        <h2>Chats</h2>
        {convsQ.isLoading && <p className="muted small">Loading…</p>}
        {convsQ.data && convsQ.data.results.length === 0 && (
          <p className="muted small">
            No chats yet — a conversation opens when either of you starts one after a shortlist.
          </p>
        )}
        {(convsQ.data?.results ?? []).map((c) => (
          <button
            key={c.id}
            className={`conv-item ${c.id === activeId ? "active" : ""}`}
            onClick={() => setActiveId(c.id)}
          >
            <span className="conv-name">{c.other_party}</span>
            {c.unread_count > 0 && <span className="unread-pill">{c.unread_count}</span>}
          </button>
        ))}
      </aside>

      <div className="thread-pane">
        {!activeId && (
          <div className="card center">
            <p className="muted">Select a conversation to start chatting.</p>
          </div>
        )}
        {activeId && (
          <div className="card thread">
            <div className="thread-head">
              <h2>{activeConv?.other_party ?? "Chat"}</h2>
              <span className="muted small">
                {wsStatus === "open"
                  ? "live"
                  : wsStatus === "connecting"
                    ? "connecting…"
                    : "reconnecting via polling"}
              </span>
            </div>
            {msgsQ.isLoading && <p className="muted small">Loading messages…</p>}
            {msgsQ.isError && <ErrorState error={msgsQ.error} retry={() => msgsQ.refetch()} />}
            <div className="thread-body">
              {messages.map((m) => {
                const mine = m.sender === user?.email;
                return (
                  <div key={m.id} className={`bubble ${mine ? "mine" : "theirs"}`}>
                    <p>{m.body}</p>
                    <span className="bubble-meta">
                      {new Date(m.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                      {mine && (m.read_at ? " · read" : " · sent")}
                    </span>
                  </div>
                );
              })}
              <div ref={bottomRef} />
            </div>
            {error && <div className="form-error">{error}</div>}
            <form
              className="composer"
              onSubmit={(e) => {
                e.preventDefault();
                if (!draft.trim()) return;
                if (!sendOverWs()) sendM.mutate();
              }}
            >
              <input
                placeholder="Type a message…"
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
              />
              <button
                className="btn primary"
                type="submit"
                disabled={!draft.trim() || (wsStatus !== "open" && sendM.isPending)}
              >
                Send
              </button>
            </form>
          </div>
        )}
      </div>
    </section>
  );
}
