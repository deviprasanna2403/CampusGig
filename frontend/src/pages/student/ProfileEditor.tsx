import { useState, type FormEvent } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  addAvailability,
  addStudentSkill,
  deleteAvailability,
  deleteStudentSkill,
  getMyStudentProfile,
  listCampuses,
  listSkills,
  updateMyStudentProfile,
} from "../../api/profiles";
import { ApiError } from "../../api/client";
import ErrorState from "../../components/ErrorState";

const DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
// Values must match the backend's TextChoices (lowercase values, capitalized labels).
const PROFICIENCY = ["beginner", "intermediate", "advanced", "expert"];

export default function ProfileEditor() {
  const queryClient = useQueryClient();
  const profileQ = useQuery({ queryKey: ["student-profile"], queryFn: getMyStudentProfile });
  const campusesQ = useQuery({ queryKey: ["campuses"], queryFn: listCampuses, staleTime: 300_000 });
  const skillsQ = useQuery({ queryKey: ["skills"], queryFn: listSkills, staleTime: 300_000 });

  const [identity, setIdentity] = useState<{ full_name: string; bio: string; resume_headline: string; year_of_study: string } | null>(null);
  const [campusId, setCampusId] = useState<string>("");
  const [identityMsg, setIdentityMsg] = useState<string | null>(null);
  const [identityErr, setIdentityErr] = useState<string | null>(null);

  const [newSkillId, setNewSkillId] = useState("");
  const [newProficiency, setNewProficiency] = useState("beginner");
  const [skillErr, setSkillErr] = useState<string | null>(null);
  const [newDay, setNewDay] = useState("5");
  const [newStart, setNewStart] = useState("10:00");
  const [newEnd, setNewEnd] = useState("14:00");
  const [availErr, setAvailErr] = useState<string | null>(null);

  const profile = profileQ.data;

  // Seed local form state once the profile arrives (uncontrolled -> controlled).
  if (profile && identity === null) {
    setIdentity({
      full_name: profile.full_name,
      bio: profile.bio,
      resume_headline: profile.resume_headline,
      year_of_study: profile.year_of_study ? String(profile.year_of_study) : "",
    });
    setCampusId(profile.campus?.id ?? "");
  }

  const saveIdentity = useMutation({
    mutationFn: () =>
      updateMyStudentProfile({
        full_name: identity!.full_name.trim(),
        bio: identity!.bio,
        resume_headline: identity!.resume_headline,
        year_of_study: identity!.year_of_study ? Number(identity!.year_of_study) : null,
        campus_id: campusId || null,
      }),
    onSuccess: () => {
      setIdentityMsg("Profile saved.");
      setIdentityErr(null);
      queryClient.invalidateQueries({ queryKey: ["student-profile"] });
      setTimeout(() => setIdentityMsg(null), 2500);
    },
    onError: (err) => setIdentityErr(err instanceof ApiError ? err.message : "Could not save profile."),
  });

  const addSkillM = useMutation({
    mutationFn: () =>
      addStudentSkill({
        skill_id: newSkillId,
        proficiency: newProficiency,
        years_of_experience: null,
      }),
    onSuccess: () => {
      setNewSkillId("");
      setSkillErr(null);
      queryClient.invalidateQueries({ queryKey: ["student-profile"] });
    },
    onError: (err) => setSkillErr(err instanceof ApiError ? err.message : "Could not add skill."),
  });

  const delSkillM = useMutation({
    mutationFn: deleteStudentSkill,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["student-profile"] }),
  });

  const addAvailM = useMutation({
    mutationFn: () => addAvailability({ day_of_week: Number(newDay), start_time: newStart, end_time: newEnd }),
    onSuccess: () => {
      setAvailErr(null);
      queryClient.invalidateQueries({ queryKey: ["student-profile"] });
    },
    onError: (err) => setAvailErr(err instanceof ApiError ? err.message : "Could not add slot."),
  });

  const delAvailM = useMutation({
    mutationFn: deleteAvailability,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["student-profile"] }),
  });

  if (profileQ.isLoading) return <div className="page-loading">Loading profile…</div>;
  if (profileQ.isError) return <ErrorState error={profileQ.error} retry={() => profileQ.refetch()} />;

  const ownedSkillIds = new Set((profile?.skills ?? []).map((s) => s.skill.id));

  function onSubmitIdentity(e: FormEvent) {
    e.preventDefault();
    saveIdentity.mutate();
  }

  return (
    <section className="profile-editor">
      <h1>My profile</h1>
      <p className="muted">
        Completion: <strong>{profile!.completion_percentage}%</strong>
        {profile!.is_complete ? " — complete 🎉" : " — add the missing pieces below"}
      </p>

      <form className="card" onSubmit={onSubmitIdentity}>
        <h2>Identity</h2>
        {identityMsg && <div className="success-note">{identityMsg}</div>}
        {identityErr && <div className="form-error">{identityErr}</div>}
        <label>
          Full name
          <input value={identity?.full_name ?? ""} onChange={(e) => setIdentity({ ...identity!, full_name: e.target.value })} />
        </label>
        <label>
          Resume headline
          <input
            value={identity?.resume_headline ?? ""}
            onChange={(e) => setIdentity({ ...identity!, resume_headline: e.target.value })}
            placeholder="e.g. B.Tech CSE '27 — event ops & design"
          />
        </label>
        <label>
          Bio
          <textarea rows={3} value={identity?.bio ?? ""} onChange={(e) => setIdentity({ ...identity!, bio: e.target.value })} />
        </label>
        <div className="range-row">
          <label>
            Campus
            <select value={campusId} onChange={(e) => setCampusId(e.target.value)}>
              <option value="">— choose campus —</option>
              {(campusesQ.data ?? []).map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name} ({c.city})
                </option>
              ))}
            </select>
          </label>
          <label>
            Year of study
            <select value={identity?.year_of_study ?? ""} onChange={(e) => setIdentity({ ...identity!, year_of_study: e.target.value })}>
              <option value="">—</option>
              {[1, 2, 3, 4, 5, 6].map((y) => (
                <option key={y} value={y}>
                  {y === 6 ? "Postgraduate" : `${y}${["st", "nd", "rd"][y - 1] ?? "th"} year`}
                </option>
              ))}
            </select>
          </label>
        </div>
        <button className="btn primary" type="submit" disabled={saveIdentity.isPending}>
          {saveIdentity.isPending ? "Saving…" : "Save profile"}
        </button>
      </form>

      <div className="card">
        <h2>Skills</h2>
        {skillErr && <div className="form-error">{skillErr}</div>}
        <div className="owned-list">
          {(profile?.skills ?? []).map((row) => (
            <span key={row.id} className="skill-tag removable">
              {row.skill.name} · {row.proficiency}
              <button type="button" aria-label={`Remove ${row.skill.name}`} onClick={() => delSkillM.mutate(row.id)}>
                ×
              </button>
            </span>
          ))}
          {(profile?.skills ?? []).length === 0 && <p className="muted small">No skills yet — add a few to complete your profile.</p>}
        </div>
        <div className="range-row">
          <label>
            Skill
            <select value={newSkillId} onChange={(e) => setNewSkillId(e.target.value)}>
              <option value="">— choose a skill —</option>
              {(skillsQ.data ?? [])
                .filter((s) => !ownedSkillIds.has(s.id))
                .map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name}
                  </option>
                ))}
            </select>
          </label>
          <label>
            Proficiency
            <select value={newProficiency} onChange={(e) => setNewProficiency(e.target.value)}>
              {PROFICIENCY.map((p) => (
            <option key={p} value={p}>
              {p.charAt(0).toUpperCase() + p.slice(1)}
            </option>
              ))}
            </select>
          </label>
          <button className="btn ghost" type="button" disabled={!newSkillId || addSkillM.isPending} onClick={() => addSkillM.mutate()}>
            Add skill
          </button>
        </div>
      </div>

      <div className="card">
        <h2>Weekly availability</h2>
        {availErr && <div className="form-error">{availErr}</div>}
        <div className="owned-list">
          {(profile?.availability ?? []).map((row) => (
            <span key={row.id} className="skill-tag removable">
              {DAYS[row.day_of_week]} {row.start_time.slice(0, 5)}–{row.end_time.slice(0, 5)}
              <button type="button" aria-label="Remove slot" onClick={() => delAvailM.mutate(row.id)}>
                ×
              </button>
            </span>
          ))}
          {(profile?.availability ?? []).length === 0 && <p className="muted small">No availability slots yet.</p>}
        </div>
        <div className="range-row">
          <label>
            Day
            <select value={newDay} onChange={(e) => setNewDay(e.target.value)}>
              {DAYS.map((d, i) => (
                <option key={i} value={i}>
                  {d}
                </option>
              ))}
            </select>
          </label>
          <label>
            From
            <input type="time" value={newStart} onChange={(e) => setNewStart(e.target.value)} />
          </label>
          <label>
            To
            <input type="time" value={newEnd} onChange={(e) => setNewEnd(e.target.value)} />
          </label>
          <button className="btn ghost" type="button" onClick={() => addAvailM.mutate()}>
            Add slot
          </button>
        </div>
        <p className="muted small">Slots that overlap an existing slot for the same day are rejected by the platform.</p>
      </div>
    </section>
  );
}
