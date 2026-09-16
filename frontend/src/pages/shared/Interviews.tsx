import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { createInterview, listInterviews, updateInterview } from "../../api/interviews";
import { listBusinessApplications } from "../../api/applications";
import { useAuth } from "../../auth/AuthContext";
import ErrorState from "../../components/ErrorState";
import StatusBadge from "../../components/jobs/StatusBadge";

function toLocalInput(date: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

export default function Interviews() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const isBusiness = user?.role === "business";
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [appId, setAppId] = useState("");
  const [startsAt, setStartsAt] = useState(toLocalInput(new Date(Date.now() + 24 * 3600 * 1000)));
  const [durationMin, setDurationMin] = useState("45");
  const [meetingUrl, setMeetingUrl] = useState("");
  const [notes, setNotes] = useState("");

  const interviewsQ = useQuery({ queryKey: ["interviews"], queryFn: () => listInterviews() });
  const shortlistedQ = useQuery({
    queryKey: ["business-applications-shortlisted"],
    queryFn: () => listBusinessApplications({ status: "INTERVIEW" }),
    enabled: isBusiness && showForm,
  });

  const createM = useMutation({
    mutationFn: () => {
      const start = new Date(startsAt);
      const end = new Date(start.getTime() + Number(durationMin) * 60_000);
      return createInterview({
        application_id: appId,
        starts_at: start.toISOString(),
        ends_at: end.toISOString(),
        timezone_name: Intl.DateTimeFormat().resolvedOptions().timeZone,
        meeting_url: meetingUrl.trim() || undefined,
        notes: notes.trim() || undefined,
      });
    },
    onSuccess: () => {
      setError(null);
      setShowForm(false);
      queryClient.invalidateQueries({ queryKey: ["interviews"] });
    },
    onError: (err) => setError(err instanceof Error ? err.message : "Could not schedule."),
  });

  const statusM = useMutation({
    mutationFn: ({ id, status }: { id: string; status: "CONFIRMED" | "DECLINED" | "COMPLETED" | "CANCELLED" }) =>
      updateInterview(id, { status }),
    onSuccess: () => {
      setError(null);
      queryClient.invalidateQueries({ queryKey: ["interviews"] });
    },
    onError: (err) => setError(err instanceof Error ? err.message : "Could not update."),
  });

  return (
    <section>
      <div className="list-head">
        <h1>Interviews</h1>
        {isBusiness && (
          <button className="btn primary" onClick={() => setShowForm(!showForm)}>
            {showForm ? "Close" : "+ Schedule interview"}
          </button>
        )}
      </div>

      {error && <div className="form-error">{error}</div>}

      {isBusiness && showForm && (
        <form
          className="card schedule-form"
          onSubmit={(e) => {
            e.preventDefault();
            createM.mutate();
          }}
        >
          <label>
            Application (interview stage)
            <select value={appId} onChange={(e) => setAppId(e.target.value)} required>
              <option value="">— choose —</option>
              {(shortlistedQ.data?.results ?? []).map((a) => (
                <option key={a.id} value={a.id}>
                  {a.student} — {a.job}
                </option>
              ))}
            </select>
          </label>
          <div className="range-row">
            <label>
              Starts at
              <input type="datetime-local" value={startsAt} onChange={(e) => setStartsAt(e.target.value)} required />
            </label>
            <label>
              Duration
              <select value={durationMin} onChange={(e) => setDurationMin(e.target.value)}>
                {["30", "45", "60", "90"].map((m) => (
                  <option key={m} value={m}>{m} min</option>
                ))}
              </select>
            </label>
          </div>
          <label>
            Meeting URL (optional)
            <input type="url" value={meetingUrl} onChange={(e) => setMeetingUrl(e.target.value)} placeholder="https://meet…" />
          </label>
          <label>
            Notes (optional)
            <textarea rows={2} value={notes} onChange={(e) => setNotes(e.target.value)} />
          </label>
          <button className="btn primary" type="submit" disabled={createM.isPending}>
            {createM.isPending ? "Scheduling…" : "Schedule"}
          </button>
        </form>
      )}

      {interviewsQ.isLoading && <div className="page-loading">Loading interviews…</div>}
      {interviewsQ.isError && <ErrorState error={interviewsQ.error} retry={() => interviewsQ.refetch()} />}

      {interviewsQ.data && (
        <div className="app-list">
          {interviewsQ.data.results.map((iv) => (
            <article key={iv.id} className="card app-row">
              <div className="app-row-main">
                <h3>
                  {new Date(iv.starts_at).toLocaleString([], {
                    weekday: "short",
                    month: "short",
                    day: "numeric",
                    hour: "2-digit",
                    minute: "2-digit",
                  })}
                  {" · "}
                  {Math.round((new Date(iv.ends_at).getTime() - new Date(iv.starts_at).getTime()) / 60000)} min
                </h3>
                <p className="muted small">
                  proposed by {iv.proposed_by}
                  {iv.timezone_name ? ` · ${iv.timezone_name}` : ""}
                </p>
                {iv.meeting_url && (
                  <p>
                    <a href={iv.meeting_url} target="_blank" rel="noreferrer">{iv.meeting_url}</a>
                  </p>
                )}
                {iv.notes && <p className="cover-note">“{iv.notes}”</p>}
              </div>
              <div className="app-row-side">
                <StatusBadge status={iv.status} />
                <div className="action-row">
                  {isBusiness && iv.status === "SCHEDULED" && (
                    <button className="btn ghost" onClick={() => statusM.mutate({ id: iv.id, status: "CANCELLED" })}>
                      Cancel
                    </button>
                  )}
                  {!isBusiness && iv.status === "SCHEDULED" && (
                    <>
                      <button className="btn primary" onClick={() => statusM.mutate({ id: iv.id, status: "CONFIRMED" })}>
                        Confirm
                      </button>
                      <button className="btn danger" onClick={() => statusM.mutate({ id: iv.id, status: "DECLINED" })}>
                        Decline
                      </button>
                    </>
                  )}
                  {iv.status === "CONFIRMED" && (
                    <button className="btn ghost" onClick={() => statusM.mutate({ id: iv.id, status: "COMPLETED" })}>
                      Mark completed
                    </button>
                  )}
                </div>
              </div>
            </article>
          ))}
          {interviewsQ.data.count === 0 && (
            <div className="card center">
              <p className="muted">No interviews yet.</p>
              {!isBusiness && <Link className="btn ghost" to="/student/applications">View applications</Link>}
            </div>
          )}
        </div>
      )}
    </section>
  );
}
