import { useState, type FormEvent } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getMyVerification, submitVerification } from "../../api/safety";
import { ApiError } from "../../api/client";
import ErrorState from "../../components/ErrorState";
import StatusBadge from "../../components/jobs/StatusBadge";

const STEPS: { key: string; label: string }[] = [
  { key: "SUBMITTED", label: "Submitted" },
  { key: "UNDER_REVIEW", label: "Under review" },
  { key: "VERIFIED", label: "Verified" },
];

const STEP_INDEX: Record<string, number> = { SUBMITTED: 0, UNDER_REVIEW: 1, VERIFIED: 2, REJECTED: 0, REVOKED: 2 };

export default function VerificationWizard() {
  const queryClient = useQueryClient();
  const verifQ = useQuery({ queryKey: ["verification"], queryFn: getMyVerification, retry: false });

  const [legalName, setLegalName] = useState<string | null>(null);
  const [regRef, setRegRef] = useState<string | null>(null);
  const [evidenceUrl, setEvidenceUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  const verif = verifQ.data;
  const editable = !!verif && (verif.status === "SUBMITTED" || verif.status === "REJECTED");
  const stepIdx = verif ? STEP_INDEX[verif.status] : 0;

  const saveM = useMutation({
    mutationFn: () =>
      submitVerification({
        // Same fallbacks the inputs display: local edits win, else existing values.
        legal_name: (legalName ?? verif?.legal_name ?? "").trim(),
        registration_reference: (regRef ?? verif?.registration_reference ?? "").trim(),
        evidence: { registration_cert: (evidenceUrl ?? verif?.evidence?.registration_cert ?? "").trim() },
      }),
    onSuccess: () => {
      setError(null);
      setSaved(true);
      queryClient.invalidateQueries({ queryKey: ["verification"] });
      queryClient.invalidateQueries({ queryKey: ["business-analytics"] });
      setTimeout(() => setSaved(false), 3000);
    },
    onError: (err) => setError(err instanceof ApiError ? (err.firstFieldError() ?? err.message) : "Could not submit."),
  });

  if (verifQ.isLoading) return <div className="page-loading">Loading verification…</div>;
  if (verifQ.isError) return <ErrorState error={verifQ.error} retry={() => verifQ.refetch()} />;

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    saveM.mutate();
  }

  return (
    <section className="profile-editor">
      <h1>Business verification</h1>
      <p className="muted">Verified businesses can publish jobs — this is the Phase 9 trust requirement.</p>

      {verif && (
        <div className="card">
          <div className="wizard-steps">
            {STEPS.map((step, i) => (
              <div key={step.key} className={`wizard-step ${i < stepIdx ? "done" : i === stepIdx ? "current" : ""}`}>
                <span className="wizard-dot" />
                <span>{step.label}</span>
              </div>
            ))}
          </div>
          <div className="wizard-status">
            <StatusBadge status={verif.status} />
            {verif.status === "REJECTED" && verif.review_notes && (
              <p className="note">Admin notes: {verif.review_notes}</p>
            )}
            {verif.status === "UNDER_REVIEW" && <p className="muted small">An admin is reviewing your documents.</p>}
            {verif.status === "VERIFIED" && <p className="muted small">You're verified — publishing is unlocked.</p>}
          </div>
        </div>
      )}

      <form className="card" onSubmit={onSubmit}>
        <h2>{editable ? (verif?.status === "REJECTED" ? "Resubmit details" : "Submit your business details") : "Submitted details"}</h2>
        {saved && <div className="success-note">Details saved — status: {verif?.status}.</div>}
        {error && <div className="form-error">{error}</div>}

        <label>
          Legal business name
          <input
            value={legalName ?? verif?.legal_name ?? ""}
            onChange={(e) => setLegalName(e.target.value)}
            disabled={!editable}
            required={editable}
          />
        </label>
        <label>
          Registration reference (CIN / GST / UEN)
          <input
            value={regRef ?? verif?.registration_reference ?? ""}
            onChange={(e) => setRegRef(e.target.value)}
            disabled={!editable}
            required={editable}
          />
        </label>
        <label>
          Evidence document URL (registration certificate)
          <input
            type="url"
            value={evidenceUrl ?? verif?.evidence?.registration_cert ?? ""}
            onChange={(e) => setEvidenceUrl(e.target.value)}
            disabled={!editable}
            required={editable}
            placeholder="https://…"
          />
        </label>

        {editable ? (
          <button className="btn primary" type="submit" disabled={saveM.isPending}>
            {saveM.isPending ? "Submitting…" : verif?.status === "REJECTED" ? "Resubmit" : "Submit for review"}
          </button>
        ) : (
          <p className="muted small">
            Details are locked while under review{verif?.status === "REVOKED" ? " (revoked — contact support)" : ""}.
          </p>
        )}
      </form>
    </section>
  );
}
