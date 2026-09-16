import { useEffect, useRef, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  listConversations,
  listMessages,
  markMessageRead,
  sendMessage,
} from "../../api/communication";
import { useAuth } from "../../auth/AuthContext";
import ErrorState from "../../components/ErrorState";

/**
 * Two-pane messaging over the REST API. No WebSocket exists in the backend
 * (Phase 7 ships polling-compatible endpoints only), so the thread polls
 * every 5 seconds while open — same pattern as the topbar bell.
 */
export default function Messages() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [activeId, setActiveId] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  const convsQ = useQuery({
    queryKey: ["conversations"],
    queryFn: listConversations,
    refetchInterval: 10_000,
  });

  const msgsQ = useQuery({
    queryKey: ["messages", activeId],
    queryFn: () => listMessages(activeId!),
    enabled: !!activeId,
    refetchInterval: 5_000,
  });

  const sendM = useMutation({
    mutationFn: () => sendMessage(activeId!, draft.trim()),
    onSuccess: () => {
      setDraft("");
      setError(null);
      queryClient.invalidateQueries({ queryKey: ["messages", activeId] });
      queryClient.invalidateQueries({ queryKey: ["conversations"] });
    },
    onError: (err) => setError(err instanceof Error ? err.message : "Could not send."),
  });

  const readM = useMutation({
    mutationFn: markMessageRead,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["messages", activeId] });
      queryClient.invalidateQueries({ queryKey: ["conversations"] });
    },
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
              <span className="muted small">chat about the shortlisted application</span>
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
                if (draft.trim()) sendM.mutate();
              }}
            >
              <input
                placeholder="Type a message…"
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
              />
              <button className="btn primary" type="submit" disabled={!draft.trim() || sendM.isPending}>
                Send
              </button>
            </form>
          </div>
        )}
      </div>
    </section>
  );
}
