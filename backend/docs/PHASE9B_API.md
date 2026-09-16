# Phase 9B API — Analytics & Audit Logs

Interactive, always-up-to-date docs are served by drf-spectacular:

- Swagger UI: `GET /api/v1/docs/`
- ReDoc: `GET /api/v1/redoc/`
- Raw OpenAPI schema: `GET /api/v1/schema/`

Phase 9B adds two cross-cutting capabilities to `apps.core` (no new app):

1. An **immutable, append-only audit trail** for consequential platform
   actions, admin-only and read-only.
2. **Analytics dashboards** (admin / business / student) built on ORM
   aggregations with date-range and interval filtering.

It does **not** touch `safety.VerificationHistory` (the verification-specific
trail) or any existing model besides adding one new table.

## What Phase 9B changed (summary)

| Area | Change |
|---|---|
| `apps/core/models.py` | New `AuditLog` model (UUID PK, actor, actor_role snapshot, action, target type/id, JSON metadata, `created_at` only — no `updated_at`) |
| `apps/core/audit.py` | New `AuditService.log()` — the ONLY writer of audit rows |
| `apps/core/views.py` / `urls.py` | New endpoints (below); `health/` untouched |
| `apps/core/admin.py` | New; `AuditLog` registered fully read-only |
| `apps/jobs/views.py` | Audit rows for publish / close / cancel / reopen |
| `apps/applications/views.py` | Audit rows for submit / withdraw / status change; **bug fix**: `serializers.ValidationError` NameError (500) on student PATCH of terminal applications |
| `apps/applications/serializers.py` | **Bug fix**: `attrs["job"]` KeyError (500) on every student application PATCH |
| `apps/safety/services.py` | One audit row in `VerificationService.transition` (references, does not duplicate, `VerificationHistory`) |
| `apps/safety/views.py` | Audit row for report review |
| Migrations | `core.0001_initial` (new `core_audit_log` table) |

## Audit trail design

**Immutability is enforced in three layers** (this codebase uses no DB
triggers):

1. Rows are written only by `AuditService.log(action, actor=None,
   target=None, metadata=None, request=None)`; the service has no update or
   delete methods.
2. The API is GET-only (list + filters; no write endpoints exist).
3. The Django admin registration is fully read-only — add/change/delete are
   all disabled (same discipline as `VerificationHistoryAdmin`).

`actor_role` snapshots the actor's role at action time; `actor` is
`SET_NULL` so user deletion preserves history. Verification decisions
appear on the generic trail as `verification.review` rows whose metadata
carries `verification_id` — `VerificationHistory` remains the domain record.

### `GET /api/v1/audit/logs/` (admin role only)

Query parameters (all optional):

| Param | Behavior |
|---|---|
| `action` | Exact match, e.g. `job.publish` |
| `target_type` | Case-insensitive: `USER` / `JOB` / `APPLICATION` / `BUSINESS_VERIFICATION` / `REPORT` |
| `target_id` | Must be a valid UUID (400 otherwise) |
| `actor` | User UUID |
| `from` / `to` | ISO dates (YYYY-MM-DD); `from` after `to` → 400 |

Paginated (project default, 20/page). Response rows:

```json
{
  "id": "0d0c8a5e-...",
  "actor": "9f2b...",
  "actor_email": "admin@example.com",
  "actor_role": "admin",
  "action": "job.publish",
  "target_type": "JOB",
  "target_id": "1111...",
  "metadata": {"title": "Gig", "from_status": "DRAFT", "to_status": "PUBLISHED", "ip": "127.0.0.1"},
  "created_at": "2026-09-15T10:30:00Z"
}
```

**Errors:** 401 unauthenticated; 403 non-admin role; 405 for any write
method (no write endpoints exist); 400 for malformed UUID/date filters.

### Audited actions (current call sites)

| Action | Where | Notes |
|---|---|---|
| `job.publish` / `job.close` / `job.cancel` / `job.reopen` | `apps/jobs/views.py` | `metadata.from_status` → `to_status`; failed actions write nothing |
| `application.submit` | `StudentApplicationListCreateView` | `metadata.job_id`, `job_title` |
| `application.withdraw` | `StudentApplicationWithdrawView` | status transition in metadata |
| `application.status_change` | `BusinessApplicationDetailView` | business-driven transitions only |
| `verification.review` | `VerificationService.transition` | metadata carries `verification_id` |
| `report.review` | `ReportAdminReviewView` | report target echoed in metadata |

Job/application creation is intentionally not audited; only lifecycle
decisions are.

## Analytics

All three dashboards share the same query contract:

| Param | Default | Validation |
|---|---|---|
| `from` | 29 days before `to` | ISO date; 400 if malformed |
| `to` | today (local) | ISO date; 400 if `from > to` |
| `interval` | `day` | one of `day`, `week`, `month` |

Aggregations are pure ORM (`Count`/`Avg`/`Trunc`) — a fixed number of
queries regardless of data volume. Every per-role summary is scoped inside
the query itself, not only by the permission class.

### `GET /api/v1/analytics/admin/` (admin role only)

```json
{
  "window": {"from": "2026-08-17", "to": "2026-09-15"},
  "interval": "day",
  "users": {"total": 12, "by_role": {"student": 8, "business": 3, "admin": 1}, "verified": 4, "new_in_window": 5},
  "jobs": {"total": 30, "by_status": {"DRAFT": 4, "PUBLISHED": 20}, "new_in_window": 7},
  "applications": {"total": 40, "by_status": {"SUBMITTED": 25, "SELECTED": 8}, "new_in_window": 10, "selection_rate": 0.2},
  "verifications": {"by_status": {"SUBMITTED": 2, "VERIFIED": 3}},
  "reports": {"by_status": {"OPEN": 1, "VALID": 2}},
  "timeseries": {"new_users": [{"date": "2026-09-01", "count": 2}], "new_jobs": [], "new_applications": []}
}
```

`selection_rate` = selected / **all** applications (not just pending
submissions); `None` when there are no applications.

### `GET /api/v1/analytics/business/me/` (business role only)

```json
{
  "window": {"from": "2026-08-17", "to": "2026-09-15"},
  "interval": "day",
  "jobs": {"total": 6, "by_status": {"PUBLISHED": 4, "CLOSED": 2}, "cancelled": 0},
  "applications": {"received": 15, "by_status": {"SUBMITTED": 9, "SELECTED": 3}, "selection_rate": 0.2},
  "rating_average": 4.25,
  "timeseries": {"applications_received": [{"date": "2026-09-10", "count": 3}]}
}
```

Counts only the requesting business's jobs and the applications they
received; `rating_average` is the mean of published reviews about the
business user (`None` when unrated).

### `GET /api/v1/analytics/student/me/` (student role only)

```json
{
  "window": {"from": "2026-08-17", "to": "2026-09-15"},
  "interval": "day",
  "profile_completion_percentage": 75,
  "applications": {"total": 8, "by_status": {"SUBMITTED": 5, "WITHDRAWN": 1, "SELECTED": 2}, "success_rate": 0.25, "withdrawn": 1},
  "completed_gigs": 2,
  "rating_average": 4.5,
  "open_jobs_near_campus": 14,
  "timeseries": {"applications_submitted": [{"date": "2026-09-12", "count": 1}]}
}
```

`open_jobs_near_campus` counts published jobs within the project's default
discovery radius of the student's **registered campus** (same
campus-based pattern as Phase 4/5 — no personal GPS data). Students
without a campus get `0`. `success_rate` is selected / all of the
student's applications.

## Role/permission summary

| Endpoint | Student | Business | Admin |
|---|---|---|---|
| `GET audit/logs/` | ❌ | ❌ | ✅ |
| `GET analytics/admin/` | ❌ | ❌ | ✅ |
| `GET analytics/business/me/` | ❌ | ✅ (own data) | ❌ |
| `GET analytics/student/me/` | ✅ (own data) | ❌ | ❌ |

All checks reuse `apps.accounts.permissions` (`IsAdminRole`, `IsBusiness`,
`IsStudent`) — no new permission classes were introduced.

## Django admin

`AuditLog` is registered in `apps/core/admin.py` strictly read-only:
`list_display` (action, actor, role, target, timestamp), filters on
action/target type/role, search by actor email/action/target id, date
hierarchy — and `has_add/change/delete_permission` all return `False`.
There is no way to create or modify audit rows through the admin.

## Tests

- `apps/core/tests/test_audit.py` (20): API permissions/filters/immutability,
  service behavior, one-row-per-action coverage for every call site, loose
  query-count guard (bounded, not single-digit, per plan).
- `apps/core/tests/test_analytics.py` (12): role gating, window/interval
  validation, aggregation math, per-role scoping.
- `apps/applications/tests/test_application_validation_regression.py` (2):
  the 500→400 regression for student PATCH on terminal and active
  applications.

## Known gaps / to-fix

**None currently open.** Deferred by design (out of Phase 9B scope):
login/auth audit events (explicitly deferred); async/queued audit writes
(writes are synchronous, matching the codebase idiom); analytics caching
or materialized views.
