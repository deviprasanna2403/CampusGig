import { useEffect, useState, type FormEvent } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { createJob, getJob, listCategories, updateJob, type JobInput } from "../../api/jobs";
import { listSkills } from "../../api/profiles";
import { ApiError } from "../../api/client";
import ErrorState from "../../components/ErrorState";

const JOB_TYPES = [
  ["ONE_DAY_GIG", "One-day gig"],
  ["WEEKEND", "Weekend"],
  ["PART_TIME", "Part-time"],
  ["TEMPORARY", "Temporary"],
  ["SEASONAL", "Seasonal"],
  ["EVENT_BASED", "Event-based"],
  ["INTERNSHIP", "Internship"],
] as const;

const PAYMENT_TYPES = [
  ["HOURLY", "Hourly"],
  ["DAILY", "Daily"],
  ["WEEKLY", "Weekly"],
  ["MONTHLY", "Monthly"],
  ["FIXED_PROJECT", "Fixed project"],
] as const;

function todayPlus(days: number): string {
  const d = new Date();
  d.setDate(d.getDate() + days);
  return d.toISOString().slice(0, 10);
}

const EMPTY: JobInput = {
  title: "",
  description: "",
  category_id: "",
  job_type: "ONE_DAY_GIG",
  required_skill_ids: [],
  location_latitude: 12.9716,
  location_longitude: 77.5946,
  start_date: todayPlus(4),
  end_date: todayPlus(4),
  start_time: "09:00",
  end_time: "17:00",
  payment_amount: "500.00",
  payment_type: "HOURLY",
  workers_required: 2,
  application_deadline: todayPlus(2),
  eligibility_notes: "",
};

export default function JobEditor() {
  const { id } = useParams<{ id: string }>();
  const editing = !!id;
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [form, setForm] = useState<JobInput | null>(editing ? null : { ...EMPTY });
  const [error, setError] = useState<string | null>(null);

  const categoriesQ = useQuery({ queryKey: ["job-categories"], queryFn: listCategories, staleTime: 300_000 });
  const skillsQ = useQuery({ queryKey: ["skills"], queryFn: listSkills, staleTime: 300_000 });
  const jobQ = useQuery({
    queryKey: ["job", id],
    queryFn: () => getJob(id!),
    enabled: editing,
    retry: false,
  });

  // Seed the form from the fetched job when editing.
  useEffect(() => {
    if (editing && jobQ.data && form === null) {
      const j = jobQ.data;
      setForm({
        title: j.title,
        description: j.description,
        category_id: j.category?.id ?? "",
        job_type: j.job_type,
        required_skill_ids: j.required_skills.map((s) => s.id),
        location_latitude: j.location_latitude ?? 12.9716,
        location_longitude: j.location_longitude ?? 77.5946,
        start_date: j.start_date,
        end_date: j.end_date,
        start_time: j.start_time.slice(0, 5),
        end_time: j.end_time.slice(0, 5),
        payment_amount: j.payment_amount,
        payment_type: j.payment_type,
        workers_required: j.workers_required,
        application_deadline: j.application_deadline,
        eligibility_notes: j.eligibility_notes,
      });
    }
  }, [editing, jobQ.data, form]); // eslint-disable-line react-hooks/exhaustive-deps

  const saveM = useMutation({
    mutationFn: (input: JobInput) => (editing ? updateJob(id!, input) : createJob(input)),
    onSuccess: (job) => {
      queryClient.invalidateQueries({ queryKey: ["my-jobs"] });
      navigate("/business/jobs", { state: { saved: job.title } });
    },
    onError: (err) =>
      setError(err instanceof ApiError ? (err.firstFieldError() ?? err.message) : "Could not save the job."),
  });

  if (editing && jobQ.isLoading) return <div className="page-loading">Loading job…</div>;
  if (editing && jobQ.isError) return <ErrorState error={jobQ.error} retry={() => jobQ.refetch()} />;
  if (!form) return <div className="page-loading">Preparing form…</div>;

  function set<K extends keyof JobInput>(key: K, value: JobInput[K]) {
    setForm({ ...form!, [key]: value });
  }

  function toggleSkill(skillId: string) {
    const ids = form!.required_skill_ids ?? [];
    set("required_skill_ids", ids.includes(skillId) ? ids.filter((x) => x !== skillId) : [...ids, skillId]);
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    saveM.mutate({ ...form!, title: form!.title.trim() });
  }

  return (
    <section className="profile-editor">
      <h1>{editing ? "Edit job" : "New job"}</h1>
      <p className="muted">Jobs start as drafts — publish from the jobs list when it's ready (requires a verified business).</p>

      <form className="card" onSubmit={onSubmit}>
        {error && <div className="form-error">{error}</div>}

        <label>
          Title
          <input value={form.title} onChange={(e) => set("title", e.target.value)} required maxLength={200} />
        </label>

        <label>
          Description
          <textarea rows={4} value={form.description} onChange={(e) => set("description", e.target.value)} required />
        </label>

        <div className="range-row">
          <label>
            Category
            <select value={form.category_id} onChange={(e) => set("category_id", e.target.value)} required>
              <option value="">— choose —</option>
              {(categoriesQ.data ?? []).map((c) => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </select>
          </label>
          <label>
            Job type
            <select value={form.job_type} onChange={(e) => set("job_type", e.target.value)}>
              {JOB_TYPES.map(([v, l]) => (
                <option key={v} value={v}>{l}</option>
              ))}
            </select>
          </label>
        </div>

        <label>
          Required skills (optional)
        </label>
        <div className="owned-list">
          {(skillsQ.data ?? []).map((s) => {
            const on = (form.required_skill_ids ?? []).includes(s.id);
            return (
              <button
                key={s.id}
                type="button"
                className={`skill-tag toggleable ${on ? "on" : ""}`}
                aria-pressed={on}
                onClick={() => toggleSkill(s.id)}
              >
                {s.name}
              </button>
            );
          })}
          {(skillsQ.data ?? []).length === 0 && <p className="muted small">No skills configured on the platform yet.</p>}
        </div>

        <div className="range-row">
          <label>
            Payment amount (₹)
            <input type="number" min="1" step="0.01" value={form.payment_amount} onChange={(e) => set("payment_amount", e.target.value)} required />
          </label>
          <label>
            Payment type
            <select value={form.payment_type} onChange={(e) => set("payment_type", e.target.value)}>
              {PAYMENT_TYPES.map(([v, l]) => (
                <option key={v} value={v}>{l}</option>
              ))}
            </select>
          </label>
          <label>
            Workers needed
            <input type="number" min="1" value={form.workers_required} onChange={(e) => set("workers_required", Number(e.target.value))} required />
          </label>
        </div>

        <div className="range-row">
          <label>
            Start date
            <input type="date" value={form.start_date} onChange={(e) => set("start_date", e.target.value)} required />
          </label>
          <label>
            End date
            <input type="date" value={form.end_date} onChange={(e) => set("end_date", e.target.value)} required />
          </label>
          <label>
            Apply-by deadline
            <input type="date" value={form.application_deadline} onChange={(e) => set("application_deadline", e.target.value)} required />
          </label>
        </div>

        <div className="range-row">
          <label>
            Start time
            <input type="time" value={form.start_time} onChange={(e) => set("start_time", e.target.value)} required />
          </label>
          <label>
            End time
            <input type="time" value={form.end_time} onChange={(e) => set("end_time", e.target.value)} required />
          </label>
        </div>

        <div className="range-row">
          <label>
            Location latitude
            <input type="number" step="any" value={form.location_latitude} onChange={(e) => set("location_latitude", Number(e.target.value))} required />
          </label>
          <label>
            Location longitude
            <input type="number" step="any" value={form.location_longitude} onChange={(e) => set("location_longitude", Number(e.target.value))} required />
          </label>
        </div>

        <label>
          Eligibility notes
          <textarea rows={2} value={form.eligibility_notes} onChange={(e) => set("eligibility_notes", e.target.value)} required placeholder="e.g. Must be enrolled in college." />
        </label>

        <div className="modal-actions">
          <button type="button" className="btn ghost" onClick={() => navigate("/business/jobs")}>Cancel</button>
          <button className="btn primary" type="submit" disabled={saveM.isPending}>
            {saveM.isPending ? "Saving…" : editing ? "Save changes" : "Create draft job"}
          </button>
        </div>
      </form>
    </section>
  );
}
