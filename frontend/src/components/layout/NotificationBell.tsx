import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { listNotifications, markNotificationRead } from "../../api/notifications";

/**
 * Bell with unread count, polling every 30s (the backend has no WebSocket;
 * REST polling keeps it simple and matches the F4 chat pattern).
 */
export default function NotificationBell() {
  const [open, setOpen] = useState(false);
  const queryClient = useQueryClient();

  const unreadQ = useQuery({
    queryKey: ["notification-bell"],
    queryFn: () => listNotifications({ unread: true, page_size: 6 }),
    refetchInterval: 30_000,
  });

  const readM = useMutation({
    mutationFn: markNotificationRead,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["notification-bell"] });
      queryClient.invalidateQueries({ queryKey: ["notifications"] });
    },
  });

  const unread = unreadQ.data?.results ?? [];
  const count = unreadQ.data?.count ?? 0;

  return (
    <div className="bell-wrap">
      <button className="bell" aria-label={`Notifications (${count} unread)`} onClick={() => setOpen(!open)}>
        🔔
        {count > 0 && <span className="bell-count">{count > 9 ? "9+" : count}</span>}
      </button>
      {open && (
        <div className="bell-dropdown card">
          <div className="bell-head">
            <strong>Notifications</strong>
            <Link to="/notifications" onClick={() => setOpen(false)}>View all</Link>
          </div>
          {unread.length === 0 && <p className="muted small">All caught up.</p>}
          {unread.map((n) => (
            <div key={n.id} className="bell-item">
              <div>
                <p className="bell-title">{n.title}</p>
                <p className="muted small">{n.body}</p>
              </div>
              <button className="btn ghost" onClick={() => readM.mutate(n.id)}>✓</button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
