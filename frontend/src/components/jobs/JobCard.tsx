import { Link } from "react-router-dom";
import type { Job } from "../../api/types";
import StatusBadge from "./StatusBadge";

const JOB_TYPE_LABEL: Record<string, string> = {
  ONE_DAY_GIG: "One-day gig",
  WEEKEND: "Weekend",
  PART_TIME: "Part-time",
  TEMPORARY: "Temporary",
  SEASONAL: "Seasonal",
  EVENT_BASED: "Event-based",
  INTERNSHIP: "Internship",
};

const PAYMENT_LABEL: Record<string, string> = {
  HOURLY: "/hr",
  DAILY: "/day",
  WEEKLY: "/wk",
  MONTHLY: "/mo",
  FIXED_PROJECT: " fixed",
};

export default function JobCard({ job }: { job: Job }) {
  return (
    <article className="card job-card">
      <div className="job-card-head">
        <h3>
          <Link to={`/student/jobs/${job.id}`}>{job.title}</Link>
        </h3>
        <StatusBadge status={job.status} />
      </div>
      <p className="job-meta">
        {job.category?.name ?? "Uncategorized"} · {JOB_TYPE_LABEL[job.job_type] ?? job.job_type} · needs{" "}
        {job.workers_required} {job.workers_required === 1 ? "person" : "people"}
      </p>
      <p className="job-desc">{job.description}</p>
      {job.required_skills.length > 0 && (
        <p className="skill-tags">
          {job.required_skills.map((s) => (
            <span key={s.id} className="skill-tag">
              {s.name}
            </span>
          ))}
        </p>
      )}
      <div className="job-card-foot">
        <span className="pay">
          ₹{job.payment_amount}
          {PAYMENT_LABEL[job.payment_type] ?? ""}
        </span>
        <span className="muted small">
          {job.start_date} → {job.end_date} · apply by {job.application_deadline}
        </span>
      </div>
    </article>
  );
}
