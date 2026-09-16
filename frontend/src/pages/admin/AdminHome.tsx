/**
 * Admin dashboard (Phase F5) — real Phase 9B platform analytics from
 * GET /core/analytics/admin/ (no mocked data). Date window + interval
 * selection, status breakdowns, and simple bar visualizations of the
 * timeseries. Queues link to the verification and reports pages.
 */

import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { getAdminAnalytics } from "../../api/admin";
import ErrorState from "../../components/ErrorState";

const INTERVALS: [("day" | "week" | "month"), string][] = [
  ["day", "Daily"],
  ["week", "Weekly"],
  ["month", "Monthly"],
];

function Stat({ label, value, sub }: { label: string; value: string | number; sub?: string | null }) {
  return (
    <div className="stat-card">
      <p className="stat-value">{value}</p>
      <p className="stat-label">{label}</p>
      {sub && <p className="stat-sub muted">{sub}</p>}
    </div>
  );
}

function MiniBars({ points, label }: { points: { date: string; count: number }[]; label: string }) {
  if (points.length === 0) return <p className="muted small">No {label} in this window.</p>;
  const max = Math.max(...points.map((p) => p.count), 1);
  return (
    <div className="mini-bars">
      {points.slice(-14).map((p) => (
        <div key={p.date} className="mini-bar-wrap" title={`${p.date}: ${p.count}`}>
          <div className="mini-bar" style={{ height: `${Math.max((p.count / max) * 100, 4)}%` }} />
          <span className="mini-bar-label">{p.date.slice(5)}</span>
        </div>
  ))}
    </div>
  );
}

function Breakdown({ title, counts }: { title: string; counts: Record<string, number> }) {
  const entries = Object.entries(counts);
  if (entries.length === 0) return <p className="muted small">None yet.</p>;
  return (
    <div className="breakdown">
      <h3>{title}</h3>
      {entries.map(([k, v]) => (
        <div key={k} className="breakdown-row">
          <span>{k.replaceAll("_", " ").toLowerCase()}</span>
          <strong>{v}</strong>
        </div>
      ))}
    </div>
  );
}

export default function AdminHome() {
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [interval, setInterval] = useState<"day" | "week" | "month">("day");

  const analyticsQ = useQuery({
    queryKey: ["admin-analytics", from, to, interval],
    queryFn: () =>
      getAdminAnalytics({
        from: from || undefined,
        to: to || undefined,
        interval,
      }),
  });

  const a = analyticsQ.data;

  return (
    <section>
      <div className="list-head">
        <h1>Platform overview</h1>
        <div className="list-head-actions">
          <label className="inline-select">
            From <input type="date" value={from} onChange={(e) => setFrom(e.target.value)} />
          </label>
          <label className="inline-select">
            To <input type="date" value={to} onChange={(e) => setTo(e.target.value)} />
          </label>
          <label className="inline-select">
            <select value={interval} onChange={(e) => setInterval(e.target.value as "day" | "week" | "month")}>
              {INTERVALS.map(([v, l]) => (
                <option key={v} value={v}>{l}</option>
              ))}
            </select>
          </label>
        </div>
      </div>

      {analyticsQ.isLoading && <div className="page-loading">Loading analytics…</div>}
      {analyticsQ.isError && <ErrorState error={analyticsQ.error} retry={() => analyticsQ.refetch()} />}

      {a && (
        <>
          <div className="stat-grid">
            <Stat label="Total users" value={a.users.total} sub={`${a.users.new_in_window} new in window`} />
            <Stat label="Verified users" value={a.users.verified} sub={`of ${a.users.total}`} />
            <Stat label="Jobs" value={a.jobs.total} sub={`${a.jobs.new_in_window} new in window`} />
            <Stat
              label="Applications"
              value={a.applications.total}
              sub={
                a.applications.selection_rate != null
                  ? `${(a.applications.selection_rate * 100).toFixed(1)}% selection rate`
                  : `${a.applications.new_in_window} new in window`
              }
            />
          </div>

          <div className="admin-panels">
            <div className="card">
              <h3>New users</h3>
              <MiniBars points={a.timeseries.new_users} label="new users" />
            </div>
            <div className="card">
              <h3>New jobs</h3>
              <MiniBars points={a.timeseries.new_jobs} label="new jobs" />
            </div>
            <div className="card">
              <h3>New applications</h3>
              <MiniBars points={a.timeseries.new_applications} label="applications" />
            </div>
          </div>

          <div className="admin-panels three">
            <Breakdown title="Users by role" counts={a.users.by_role} />
            <Breakdown title="Verifications by status" counts={a.verifications.by_status} />
            <Breakdown title="Reports by status" counts={a.reports.by_status} />
          </div>

          <div className="queue-links">
            <Link className="btn primary" to="/admin/verifications">Verification queue</Link>
            <Link className="btn ghost" to="/admin/reports">Report moderation</Link>
            <Link className="btn ghost" to="/admin/audit-logs">Audit log</Link>
          </div>
        </>
      )}
    </section>
  );
}
