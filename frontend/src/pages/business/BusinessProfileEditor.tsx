import { useState, type FormEvent } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getMyBusinessProfile, listCampuses, updateMyBusinessProfile } from "../../api/profiles";
import { ApiError } from "../../api/client";
import ErrorState from "../../components/ErrorState";

export default function BusinessProfileEditor() {
  const queryClient = useQueryClient();
  const profileQ = useQuery({ queryKey: ["business-profile"], queryFn: getMyBusinessProfile });
  const campusesQ = useQuery({ queryKey: ["campuses"], queryFn: listCampuses, staleTime: 300_000 });

  const [form, setForm] = useState<{
    business_name: string; description: string; website: string; industry: string;
  } | null>(null);
  const [campusId, setCampusId] = useState<string>("");
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  const profile = profileQ.data;

  if (profile && form === null) {
    setForm({
      business_name: profile.business_name,
      description: profile.description,
      website: profile.website,
      industry: profile.industry,
    });
    setCampusId(profile.campus?.id ?? "");
  }

  const saveM = useMutation({
    mutationFn: () =>
      updateMyBusinessProfile({
        business_name: form!.business_name.trim(),
        description: form!.description,
        website: form!.website.trim(),
        industry: form!.industry.trim(),
        campus_id: campusId || null,
      }),
    onSuccess: () => {
      setError(null);
      setSaved(true);
      queryClient.invalidateQueries({ queryKey: ["business-profile"] });
      setTimeout(() => setSaved(false), 2500);
    },
    onError: (err) => setError(err instanceof ApiError ? (err.firstFieldError() ?? err.message) : "Could not save."),
  });

  if (profileQ.isLoading) return <div className="page-loading">Loading profile…</div>;
  if (profileQ.isError) return <ErrorState error={profileQ.error} retry={() => profileQ.refetch()} />;

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    saveM.mutate();
  }

  return (
    <section className="profile-editor">
      <h1>Business profile</h1>
      <p className="muted">
        Completion: <strong>{profile!.completion_percentage}%</strong>
        {profile!.is_complete ? " — complete 🎉" : " (name, description, campus)"}
      </p>

      <form className="card" onSubmit={onSubmit}>
        {saved && <div className="success-note">Profile saved.</div>}
        {error && <div className="form-error">{error}</div>}

        <label>
          Business name
          <input value={form?.business_name ?? ""} onChange={(e) => setForm({ ...form!, business_name: e.target.value })} required />
        </label>
        <label>
          Description
          <textarea rows={4} value={form?.description ?? ""} onChange={(e) => setForm({ ...form!, description: e.target.value })} placeholder="What does your business do?" />
        </label>
        <div className="range-row">
          <label>
            Website
            <input type="url" value={form?.website ?? ""} onChange={(e) => setForm({ ...form!, website: e.target.value })} placeholder="https://…" />
          </label>
          <label>
            Industry
            <input value={form?.industry ?? ""} onChange={(e) => setForm({ ...form!, industry: e.target.value })} placeholder="e.g. Events, Retail" />
          </label>
        </div>
        <label>
          Primary campus (discovery reference point)
          <select value={campusId} onChange={(e) => setCampusId(e.target.value)}>
            <option value="">— choose campus —</option>
            {(campusesQ.data ?? []).map((c) => (
              <option key={c.id} value={c.id}>{c.name} ({c.city})</option>
            ))}
          </select>
        </label>

        <button className="btn primary" type="submit" disabled={saveM.isPending}>
          {saveM.isPending ? "Saving…" : "Save profile"}
        </button>
      </form>
    </section>
  );
}
