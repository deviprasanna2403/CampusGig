# Phase 9 API — Business Verification Integration & Lifecycle

Interactive, always-up-to-date docs are already served by drf-spectacular
(installed in Phase 3, unchanged here):

- Swagger UI: `GET /api/v1/docs/`
- ReDoc: `GET /api/v1/redoc/`
- Raw OpenAPI schema: `GET /api/v1/schema/`

Phase 9 does **not** introduce a new app. Business verification already
exists in `apps.safety` (Phase 8); Phase 9 integrates it with the rest of
the platform and hardens its lifecycle. All endpoints below live under
`/api/v1/safety/` and require `Authorization: Bearer <access_token>`.
Error responses use the existing project-wide envelope
(`apps.core.exceptions.custom_exception_handler`).

## What Phase 9 changed (summary)

1. **The verified flag is now actually synced.** Every admin status
   transition on a `BusinessVerification` sets the business user's
   `User.is_verified` flag (`VERIFIED` → `True`, `REJECTED`/`REVOKED` →
   `False`). Previously nothing in the codebase ever set the flag, so the
   Phase 5 publish gate could never open through the real workflow.
   A one-time data migration (`safety.0003_backfill_verified_businesses`)
   backfills existing `VERIFIED` businesses.
2. **No fast-track.** A submission must pass through `UNDER_REVIEW` before
   an admin can `VERIFIED`/`REJECTED` it. `SUBMITTED → VERIFIED` (or
   `→ REJECTED`) is now a `400`.
3. **Revocation.** `VERIFIED → REVOKED` is the only exit from verified;
   revocation is admin-only and requires review notes. A revoked business
   cannot self-resubmit (terminal; contact support).
4. **Notifications.** The business is notified on `VERIFIED`,
   `REJECTED`, and `REVOKED` (`VERIFICATION_VERIFIED` /
   `VERIFICATION_REJECTED` / `VERIFICATION_REVOKED` events, Phase 7
   notification center).
5. **Audit integrity.** All transitions flow through
   `VerificationService.transition()`, which writes the
   `VerificationHistory` row, syncs `is_verified`, and notifies inside one
   transaction. `VerificationHistory` is immutable via Django admin; the
   admin change form for `BusinessVerification` has `status`/
   `reviewed_by`/`reviewed_at` readonly so admin-form edits cannot bypass
   the service.

## Business verification (business-owned)

### `GET/PATCH /api/v1/safety/verification/`

- **Business role only.** `GET` lazily creates the verification row
  (`SUBMITTED`, `legal_name` defaulted from the business profile) on first
  access — there is no separate create step.
- `PATCH` body: `legal_name` (required), `registration_reference`
  (optional), `evidence` (JSON object; must be an object if present).
- Allowed while the status is `SUBMITTED` (the PATCH *is* the initial
  submission act) or `REJECTED` (resubmission — resets the row to
  `SUBMITTED`). `UNDER_REVIEW`, `VERIFIED`, and `REVOKED` rows are locked:
  `400` with `"This verification is under review, verified, or revoked
  and cannot be changed here."`

### `GET /api/v1/safety/admin/verifications/`

- **Admin role only.** Lists all verifications with business, status,
  reviewer, and timestamps.

### `PATCH /api/v1/safety/admin/verifications/{id}/review/`

- **Admin role only.** Body: `status`
  (`UNDER_REVIEW` / `VERIFIED` / `REJECTED`), `review_notes` (optional).
- The transition map is enforced server-side (service layer):

  | From | Allowed targets |
  |---|---|
  | `SUBMITTED` | `UNDER_REVIEW` |
  | `UNDER_REVIEW` | `VERIFIED`, `REJECTED` |
  | `VERIFIED` | `REVOKED` (via the revoke endpoint) |
  | `REJECTED` | — (resubmit via the business endpoint) |
  | `REVOKED` | — (terminal) |

  An illegal target returns `400` with
  `"Invalid status transition from {old} to {new}."`
- On success the endpoint returns the updated verification and, as a side
  effect of the service call: a `VerificationHistory` row
  (`from_status` → `to_status`, `changed_by`, notes), the synced
  `User.is_verified` flag, and the decision notification.

### `PATCH /api/v1/safety/admin/verifications/{id}/revoke/`

- **Admin role only.** New in Phase 9. Revokes a `VERIFIED` verification
  (e.g. after a valid `FAKE_BUSINESS` report). Body: `review_notes`
  (**mandatory** — `400` `"Revocation requires review notes."` if blank).
- Only `VERIFIED` rows can be revoked (`400` otherwise). Revocation sets
  `User.is_verified = False`, writes history, and sends
  `VERIFICATION_REVOKED`. Any job published by the business stays
  published — admins close/cancel jobs explicitly via the Phase 5
  endpoints.

## Notifications (Phase 7 events)

| Event | Fired when |
|---|---|
| `VERIFICATION_VERIFIED` | admin approves (`→ VERIFIED`) |
| `VERIFICATION_REJECTED` | admin rejects (`UNDER_REVIEW → REJECTED`) |
| `VERIFICATION_REVOKED` | admin revokes (`VERIFIED → REVOKED`) |

Each notification carries `{"verification_id": "<uuid>"}` in its payload
and is delivered through the existing Phase 7 channel (in-app; email when
`PHASE7_EMAIL_NOTIFICATIONS` is enabled).

## Relationship to the Phase 5 publish gate

The jobs `publish` action requires a **verified** business
(`IsVerified`, reading `User.is_verified`). With Phase 9, that flag is
earned only through the real workflow above — there is no shortcut.
End-to-end: submit → admin `UNDER_REVIEW` → admin `VERIFIED` → the
business can now `POST /api/v1/jobs/jobs/{id}/publish/`. See
`docs/PHASE5_API.md` for the publish contract.

## Django admin

- `BusinessVerification`: review-queue list (status filter, search by
  business name / user email / legal name / registration reference,
  date hierarchy on reviewed). `status`, `reviewed_by`, `reviewed_at`,
  and `business` are readonly in the form — status changes must go
  through the API/service so history, flag sync, and notifications all
  happen.
- `VerificationHistory`: **immutable** (add/change/delete all disabled);
  readable with filters and search for audit purposes.
- `Report`, `Review`, `RiskAssessment`, `TrustScoreSnapshot`: gained
  list/filter/search configuration; snapshots are readonly.

## Role/permission summary

| Endpoint | Student | Business | Admin |
|---|---|---|---|
| `GET/PATCH verification/` | ❌ | ✅ (own row) | ❌ |
| `GET admin/verifications/` | ❌ | ❌ | ✅ |
| `PATCH admin/verifications/{id}/review/` | ❌ | ❌ | ✅ |
| `PATCH admin/verifications/{id}/revoke/` | ❌ | ❌ | ✅ |

All checks reuse `apps.accounts.permissions` (`IsBusiness`,
`IsAdminRole`) — no new permission classes were introduced.

## Known gaps / to-fix

**None currently open.** Deferred by design (out of Phase 9 scope):
verification expiry / periodic re-verification; document OCR or external
KYC provider integration; student email-verification (separate concern
from business KYC).
