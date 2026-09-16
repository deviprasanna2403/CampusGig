const STATUS_CLASS: Record<string, string> = {
  DRAFT: "st-muted",
  PUBLISHED: "st-open",
  OPEN: "st-open",
  FULL: "st-warn",
  IN_PROGRESS: "st-info",
  COMPLETED: "st-success",
  CLOSED: "st-muted",
  CANCELLED: "st-danger",
  EXPIRED: "st-muted",
  SUBMITTED: "st-info",
  SELECTED: "st-success",
  REJECTED: "st-danger",
  WITHDRAWN: "st-muted",
};

export default function StatusBadge({ status }: { status: string }) {
  return <span className={`status-badge ${STATUS_CLASS[status] ?? "st-muted"}`}>{status.replaceAll("_", " ")}</span>;
}
