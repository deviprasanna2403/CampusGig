import { ApiError } from "../api/client";

/** Shared error display: uses the envelope message when available. */
export default function ErrorState({ error, retry }: { error: unknown; retry?: () => void }) {
  const message =
    error instanceof ApiError ? error.message : error instanceof Error ? error.message : "Something went wrong.";
  return (
    <div className="card center">
      <p className="form-error">{message}</p>
      {retry && (
        <button className="btn ghost" onClick={retry}>
          Try again
        </button>
      )}
    </div>
  );
}
