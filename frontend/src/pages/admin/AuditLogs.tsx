/**
 * Audit-log viewer (Phase F5) — read-only admin view of the immutable
 * Phase 9B audit trail (GET /core/audit/logs/). Filters: action,
 * target_type, target_id, actor, from/to date window. Server-side
 * pagination. No write operations exist by design.
 */

import { useState } from "react";
import { useQuery, keepPreviousData } from "@tanstack/react-query";
import { listAuditLogs } from "../../api/admin";
import type { AuditLog } from "../../api/types";
import ErrorState from "../../components/ErrorState";
import Pagination from "../../components/Pagination";

const TARGET_TYPES = ["JOB", "BUSINESS", "USER", "APPLICATION", "MESSAGE", "REPORT", "BUSINESSVERIFICATION"] as const;

function Meta({ meta }: { meta: Record<string, unknown> }) {
  const entries = Object.entries(meta);
  if (entries.length === 0) return null;
  return (
    <p className="audit-meta muted small">
      {entries.map(([k, v]) => (
        <span key={k} className="audit-meta-item">
          <strong>{k}</strong> {String(v)}
        </span>
      ))}
    </p>
  );
}

export default function AuditLogs() {
  const [action, setAction] = useState("");
  const [targetType, setTargetType] = useState("");
  const [targetId, setTargetId] = useState("");
  const [actor, setActor] = useState("");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [page, setPage] = useState(1);

  const logsQ = useQuery({
    queryKey: ["audit-logs", action, targetType, targetId, actor, from, to, page],
    queryFn: () =>
      listAuditLogs({
        action: action || undefined,
        target_type: targetType || undefined,
        target_id: targetId || undefined,
        actor: actor || undefined,
        from: from || undefined,
        to: to || undefined,
        page,
      }),
    placeholderData: keepPreviousData,
    retry: false,
  });

  const setFilter = (apply: () => void) => {
    apply();
    setPage(1);
  };

  return (
    <section>
      <div className="list-head">
        <h1>Audit log</h1>
        <p className="muted small">Immutable trail — appended by the platform only.</p>
      </div>

      <form
        className="card filter-grid"
        onSubmit={(e) => { e.preventDefault(); setPage(1); }}
      >
        <label>
          Action
          <input
            type="text"
            placeholder="e.g. verification.transition"
            value={action}
            onChange={(e) => setFilter(() => setAction(e.target.value))}
          />
        </label>
        <label>
          Target type
          <select value={targetType} onChange={(e) => setFilter(() => setTargetType(e.target.value))}>
            <option value="">All</option>
            {TARGET_TYPES.map((t) => (
              <option key={t} value={t}>{t.replaceAll("_", " ")}</option>
            ))}
          </select>
        </label>
        <label>
          Target ID
          <input
            type="text"
            placeholder="UUID"
            value={targetId}
            onChange={(e) => setTargetId(e.target.value)}
          />
        </label>
        <label>
          Actor ID
          <input
            type="text"
            placeholder="UUID"
            value={actor}
            onChange={(e) => setActor(e.target.value)}
          />
        </label>
        <label>
          From
          <input type="date" value={from} onChange={(e) => setFilter(() => setFrom(e.target.value))} />
        </label>
        <label>
          To
          <input type="date" value={to} onChange={(e) => setFilter(() => setTo(e.target.value))} />
        </label>
        <button
          type="button"
          className="btn ghost"
          onClick={() => {
            setAction(""); setTargetType(""); setTargetId(""); setActor(""); setFrom(""); setTo("");
            setPage(1);
          }}
        >
          Clear
        </button>
      </form>

      {logsQ.isLoading && <div className="page-loading">Loading audit logs…</div>}
      {logsQ.isError && <ErrorState error={logsQ.error} retry={() => logsQ.refetch()} />}

      {logsQ.data && (
        <div className="app-list">
          {logsQ.data.items.map((log: AuditLog) => (
            <article key={log.id} className="card audit-row">
              <div className="audit-row-head">
                <span className="audit-action">{log.action}</span>
                <time className="muted small">{new Date(log.created_at).toLocaleString()}</time>
              </div>
              <p className="small">
                <strong>{log.actor_email ?? "system"}</strong>
                <span className="muted"> ({log.actor_role.toLowerCase()})</span>
                {" → "}
                {log.target_type.toLowerCase()} {log.target_id ? log.target_id.slice(0, 8) + "…" : ""}
              </p>
              <Meta meta={log.metadata} />
            </article>
          ))}
          {logsQ.data.count === 0 && (
            <div className="card center"><p className="muted">No audit entries match these filters.</p></div>
          )}
          <Pagination count={logsQ.data.count} page={page} onPage={setPage} />
        </div>
      )}
    </section>
  );
}
