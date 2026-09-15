# Phase 8 API - Trust and Safety

Phase 8 adds verification, reputation, reports, reviews, and explainable risk
assessment. It does not begin Phase 9.

## Business verification

- `GET/PATCH /api/v1/safety/verification/` is business-owned.
- `GET /api/v1/safety/admin/verifications/` is admin-only.
- `PATCH /api/v1/safety/admin/verifications/{id}/review/` is admin-only.

Workflow: `SUBMITTED -> UNDER_REVIEW -> VERIFIED` or `REJECTED`.
Every admin transition creates `VerificationHistory`. Verification is not
inferred from user-supplied fields; only an admin transition to `VERIFIED`
counts as verified.

## Trust and reputation

- `GET /api/v1/safety/trust/me/` calculates a fresh explainable score for the
  authenticated user.

The rule-based business score uses verified status, selected completed jobs,
published reviews, valid reports, and cancellations. Student reputation uses
selected completed gigs, published ratings, valid reports, and withdrawals.
Scores are persisted as snapshots with component explanations and strategy keys.

## Reports

- `POST/GET /api/v1/safety/reports/` creates and lists the caller's reports.
- `GET /api/v1/safety/reports/{id}/` is limited to the reporter or an admin.
- `PATCH /api/v1/safety/admin/reports/{id}/review/` is admin-only.

Supported categories include fake jobs/scams, harassment, payment issues, fake
businesses, inappropriate content, and other. Target IDs are UUIDs and are
validated against the selected target type.

## Reviews

- `POST/GET /api/v1/safety/reviews/{user_id}/` creates or lists reviews for a
  user.

A review requires the reviewer and reviewee to be the two participants of a
`SELECTED` application whose job is `CLOSED` or `EXPIRED`. Ratings are 1-5 and
one review per participant per application is enforced at the database level.

## Risk assessment

- `POST /api/v1/safety/admin/risk/jobs/{job_id}/calculate/` calculates an admin-only
  job risk assessment.
- `GET /api/v1/safety/admin/risk/{id}/` reads an admin-only assessment.

The current strategy is `rule_based_safety_v1`. It checks unverified businesses,
external-payment language, and valid reports. It is deterministic and
explainable, not machine-learning AI, and is replaceable by a future strategy.
