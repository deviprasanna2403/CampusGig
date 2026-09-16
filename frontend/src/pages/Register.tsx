import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ApiError } from "../api/client";
import type { ApiErrorDetails } from "../api/types";
import { useAuth } from "../auth/AuthContext";

type RegisterRole = "student" | "business";

export default function Register() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [role, setRole] = useState<RegisterRole>("student");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [passwordConfirm, setPasswordConfirm] = useState("");
  const [fieldErrors, setFieldErrors] = useState<ApiErrorDetails>({});
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setFieldErrors({});
    setBusy(true);
    try {
      await register({
        email: email.trim(),
        password,
        password_confirm: passwordConfirm,
        role,
        phone: phone.trim() || undefined,
      });
      navigate("/redirect", { replace: true });
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
        if (err.details) setFieldErrors(err.details);
      } else {
        setError("Registration failed. Try again.");
      }
    } finally {
      setBusy(false);
    }
  }

  function fieldError(name: string): string | null {
    const v = fieldErrors[name];
    if (!v) return null;
    return Array.isArray(v) ? v[0] : String(v);
  }

  return (
    <main className="auth-page">
      <form className="auth-card" onSubmit={onSubmit}>
        <h1 className="brand">CampusGig</h1>
        <p className="muted">Create your account</p>

        {error && <div className="form-error">{error}</div>}

        <div className="role-toggle" role="radiogroup" aria-label="Account type">
          {(["student", "business"] as const).map((r) => (
            <button
              key={r}
              type="button"
              className={`role-option ${role === r ? "selected" : ""}`}
              aria-pressed={role === r}
              onClick={() => setRole(r)}
            >
              {r === "student" ? "I'm a student" : "I'm a business"}
            </button>
          ))}
        </div>

        <label>
          Email
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
          {fieldError("email") && <span className="field-error">{fieldError("email")}</span>}
        </label>

        <label>
          Phone (optional)
          <input
            type="tel"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            placeholder="+919876543210"
          />
          {fieldError("phone") && <span className="field-error">{fieldError("phone")}</span>}
        </label>

        <label>
          Password
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="new-password"
            required
          />
          {fieldError("password") && <span className="field-error">{fieldError("password")}</span>}
        </label>

        <label>
          Confirm password
          <input
            type="password"
            value={passwordConfirm}
            onChange={(e) => setPasswordConfirm(e.target.value)}
            autoComplete="new-password"
            required
          />
          {fieldError("password_confirm") && (
            <span className="field-error">{fieldError("password_confirm")}</span>
          )}
        </label>

        <button className="btn primary" type="submit" disabled={busy}>
          {busy ? "Creating account…" : `Register as ${role}`}
        </button>

        <p className="muted small">
          Already registered? <Link to="/login">Sign in</Link>
        </p>
      </form>
    </main>
  );
}
