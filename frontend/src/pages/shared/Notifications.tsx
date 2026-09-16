import { useState } from "react";
import { useQuery, useMutation, useQueryClient, keepPreviousData } from "@tanstack/react-query";
import { listNotifications, markNotificationRead } from "../../api/notifications";
import ErrorState from "../../components/ErrorState";
import Pagination from "../../components/Pagination";

const EVENT_LABEL: Record<string, string> = {
  APPLICATION_SUBMITTED: "Application",
  APPLICATION_SHORTLISTED: "Shortlisted",
  NEW_APPLICATION: "New applicant",
  APPLICATION_WITHDRAWN: "Withdrawn",
  INTERVIEW_SCHEDULED: "Interview",
  INTERVIEW_UPDATED: "Interview update",
  INTERVIEW_RESPONSE: "Message",
  SELECTED: "Selected",
  REJECTED: "Rejected",
  JOB_CANCELLED: "Job cancelled",
  JOB_DEADLINE_REMINDER: "Reminder",
  VERIFICATION_VERIFIED: "Verified",
  VERIFICATION_REJECTED: "Verification rejected",
  VERIFICATION_REVOKED: "Verification revoked",
};

export default function Notifications() {
  const queryClient = useQueryClient();
  const [unreadOnly, setUnreadOnly] = useState(false);
  const [page, setPage] = useState(1);

  const notifsQ = useQuery({
    queryKey: ["notifications", unreadOnly, page],
    queryFn: () => listNotifications({ unread: unreadOnly || undefined, page, page_size: 20 }),
    placeholderData: keepPreviousData,
  });

  const readM = useMutation({
    mutationFn: markNotificationRead,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["notifications"] });
      queryClient.invalidateQueries({ queryKey: ["notification-bell"] });
    },
  });

  return (
    <section>
      <div className="list-head">
        <h1>Notifications</h1>
        <label className="inline-select">
          <select value={unreadOnly ? "1" : ""} onChange={(e) => { setUnreadOnly(e.target.value === "1"); setPage(1); }}>
            <option value="">All</option>
            <option value="1">Unread only</option>
          </select>
        </label>
      </div>

      {notifsQ.isLoading && <div className="page-loading">Loading…</div>}
      {notifsQ.isError && <ErrorState error={notifsQ.error} retry={() => notifsQ.refetch()} />}

      {notifsQ.data && (
        <>
          <div className="app-list">
            {notifsQ.data.results.map((n) => (
              <article key={n.id} className={`card app-row notif-row ${n.read_at ? "" : "unread"}`}>
                <div className="app-row-main">
                  <span className="skill-tag">{EVENT_LABEL[n.event] ?? n.event}</span>
                  <h3>{n.title}</h3>
                  <p className="muted small">{n.body}</p>
                </div>
                <div className="app-row-side">
                  <span className="muted small">{new Date(n.created_at).toLocaleString()}</span>
                  {!n.read_at && (
                    <button className="btn ghost" onClick={() => readM.mutate(n.id)}>
                      Mark read
                    </button>
                  )}
                </div>
              </article>
            ))}
          </div>
          {notifsQ.data.count === 0 && (
            <div className="card center">
              <p className="muted">{unreadOnly ? "All caught up — nothing unread." : "No notifications yet."}</p>
            </div>
          )}
          <Pagination count={notifsQ.data.count} page={page} onPage={setPage} />
        </>
      )}
    </section>
  );
}
