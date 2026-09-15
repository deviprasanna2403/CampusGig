# Phase 5 API — Jobs Marketplace

Interactive, always-up-to-date docs are already served by drf-spectacular
(installed in Phase 3, unchanged here):

- Swagger UI: `GET /api/v1/docs/`
- ReDoc: `GET /api/v1/redoc/`
- Raw OpenAPI schema: `GET /api/v1/schema/`

This file is a human-readable summary of what Phase 5 adds on top of that.
All endpoints below live under `/api/v1/jobs/` and require
`Authorization: Bearer <access_token>` (from Phase 3's auth endpoints)
unless noted. Error responses use the existing project-wide envelope
(`apps.core.exceptions.custom_exception_handler`):

```json
{
  "success": false,
  "data": null,
  "error": { "code": 400, "message": "...", "details": { "...": ["..."] } }
}
```

Two error shapes come out of the handler:

- **Serializer validation errors** → `message` is always
  `"Validation failed."` and `details` carries the field-level errors.
- **Single-detail errors** (authentication, permission, 404, throttling) →
  `message` is the detail string and `details` is `null`.

Success responses are returned as-is (no envelope). Unhandled non-DRF
exceptions fall through to Django's normal 500 handling. Exception: the
four lifecycle actions (`publish`/`close`/`cancel`/`reopen`) and `nearby`
build their error responses by hand in the view — same envelope shape,
with `details: null` and the exact messages documented below.

List/retrieve responses are paginated with the project default
(20 per page): `{ "count": ..., "next": ..., "previous": ..., "results": [...] }`.

## Reference data

### `GET/POST /api/v1/jobs/categories/`, `GET/PATCH/DELETE /api/v1/jobs/categories/{id}/`

- Read (list/retrieve): any authenticated role. Only active categories are
  returned.
- Write (create/update/delete): **staff users only** (`IsAdminUser`, i.e.
  Django's `is_staff` flag — deliberately not the same check as CampusGig's
  `role == ADMIN`).
- Fields: `name` (unique, case-insensitive; blank rejected), `description`,
  `is_active`.
- Twelve categories are seeded by migration (`0002_seed_categories`): Food &
  Restaurants, Retail / Supermarkets / Marts, Events, Technology, Education,
  Digital Marketing, Logistics, Local Business, Marketing, Creative / Media,
  Office / Administration, Seasonal / Festival.
- `DELETE` hard-deletes. A category referenced by any job cannot be deleted
  (`Job.category` is `on_delete=PROTECT`); the API surfaces that as a clean
  **409 Conflict**:

```json
{ "success": false, "data": null, "error": { "code": 409,
  "message": "This category is referenced by one or more jobs and cannot be deleted.",
  "details": null } }
```

```json
// POST /api/v1/jobs/categories/
{ "name": "Tutoring", "description": "Academic help gigs" }
// 201
{
  "id": "9f1c3a2e-...", "name": "Tutoring",
  "description": "Academic help gigs", "is_active": true,
  "created_at": "...", "updated_at": "..."
}
// Duplicate name (case-insensitive match) → 400
{ "success": false, "data": null, "error": { "code": 400,
  "message": "Validation failed.",
  "details": { "name": ["A category with this name already exists."] } } }
```

## Jobs

### `POST /api/v1/jobs/jobs/` — create (draft)

- **Business role only.** The job is owned by the caller's `BusinessProfile`
  (Phase 4); a business account without a profile is rejected with `400`.
  Every job starts in `DRAFT` regardless of any `status` in the payload.
- Body fields:
  - `title` (required, trimmed non-empty)
  - `description` (required)
  - `category` — **name** of an active category, case-insensitive
    (e.g. `"events"`); a UUID in `category_id` is accepted as an alternative
  - `job_type` — `ONE_DAY_GIG` (default) / `WEEKEND` / `PART_TIME` /
    `TEMPORARY` / `SEASONAL` / `EVENT_BASED` / `INTERNSHIP`
  - `required_skill_ids` — optional list of active Skill UUIDs
  - `location_latitude` + `location_longitude` — both required together
    (WGS84 decimal degrees, validated to `[-90, 90]` / `[-180, 180]`); stored
    as a PostGIS `PointField(geography=True, srid=4326)`. The client never
    handles WKT/GeoJSON.
  - `start_date`, `end_date` (ISO dates; `end_date >= start_date`)
  - `start_time`, `end_time` (`HH:MM:SS`; `end_time > start_time`)
  - `payment_amount` (decimal > 0), `payment_type` — `HOURLY` (default) /
    `DAILY` / `WEEKLY` / `MONTHLY` / `FIXED_PROJECT`
  - `workers_required` (integer >= 1)
  - `application_deadline` (ISO date; must be on or before `start_date`)
  - `eligibility_notes` (required)
- Cross-field rules are enforced at three layers — serializer, model
  `clean()`, and database `CheckConstraint`s — so no code path can persist
  an invalid job.

```json
// POST /api/v1/jobs/jobs/
{
  "title": "Campus Event Helper",
  "description": "Help manage event operations.",
  "category": "events",
  "job_type": "ONE_DAY_GIG",
  "payment_type": "HOURLY",
  "payment_amount": "500.00",
  "location_latitude": 12.9716,
  "location_longitude": 77.5946,
  "start_date": "2026-09-20",
  "end_date": "2026-09-20",
  "start_time": "09:00:00",
  "end_time": "17:00:00",
  "workers_required": 3,
  "application_deadline": "2026-09-18",
  "eligibility_notes": "Must be enrolled in college."
}
// 201 — read fields only (category resolved from the name):
{
  "id": "b3a1...", "business": "biz@example.com",
  "title": "Campus Event Helper",
  "description": "Help manage event operations.",
  "category": { "id": "7c0d...", "name": "Events", "...": "..." },
  "job_type": "ONE_DAY_GIG",
  "required_skills": [],
  "location_latitude": 12.9716, "location_longitude": 77.5946,
  "start_date": "2026-09-20", "end_date": "2026-09-20",
  "start_time": "09:00:00", "end_time": "17:00:00",
  "payment_amount": "500.00", "payment_type": "HOURLY",
  "workers_required": 3,
  "application_deadline": "2026-09-18",
  "eligibility_notes": "Must be enrolled in college.",
  "status": "DRAFT", "created_at": "...", "updated_at": "..."
}
```

Confirmed error behavior (all `400`, `message: "Validation failed."`):
missing `description`/`eligibility_notes`/dates/times/`application_deadline`
(`"This field is required."`); `payment_amount <= 0`
(`"payment_amount must be positive."`); `workers_required < 1`
(`"workers_required must be positive."`); `application_deadline >
start_date` (`"application_deadline must be on or before start_date."`);
`end_date < start_date`; `end_time <= start_time`; missing location
coordinates (`"A valid job location is required."`) or out-of-range lat/lon
(`"Ensure this value is ..."`); unknown/inactive category name
(`"Category is invalid or inactive."`); a business account with no
BusinessProfile (`"Business profile is required before creating jobs."`).
A student calling create gets `403` via `IsBusiness`:
`message: "This action is only available to business accounts."`,
`details: null`.

### `GET /api/v1/jobs/jobs/` — list + search/filter/sort

- Any authenticated role; the queryset is scoped by role first:
  - **Business** sees only its own jobs (any status, including `DRAFT`).
  - **Student** sees only `PUBLISHED` and `OPEN` jobs.
  - **Admin** sees everything.
- Filters (query params, combinable):
  - `category` — case-insensitive category name
  - `job_type`, `payment_type`, `status` — exact match. Note: `status`
    cannot widen visibility — the role pre-filter runs first, so a student
    filtering `?status=DRAFT` simply gets zero rows rather than an error.
  - `min_payment` / `max_payment` — `payment_amount` bounds
  - `date` — jobs running on that date (`start_date <= date <= end_date`)
  - `skill` — case-insensitive skill name
- Sort via `?sort=`:
  - `newest` (default) — `created_at` descending
  - `payment` — `payment_amount` descending
  - `deadline` — `application_deadline` ascending
  - `distance` — nearest first; requires a reference campus (see Discovery)
- Paginated (20/page).

```
GET /api/v1/jobs/jobs/?category=events&payment_type=HOURLY&min_payment=200&sort=deadline
```

### `GET /api/v1/jobs/jobs/{id}/` — detail

- Same role scoping as the list. A student requesting a `DRAFT`/`FULL`/
  `CLOSED` job gets `404`, and a business requesting another business's job
  gets `404` — deliberately not `403`, so IDs can't be probed for existence
  (same convention as Phase 4's self-scoped profile rows). A malformed UUID
  also yields `404` (handled in the viewset's `get_object`), envelope:
  `message: "Not found."`, `details: null`.
- Response fields: `id`, `business` (owner account email), `title`,
  `description`, `category` (nested), `job_type`, `required_skills`
  (`[{id, name}]`), `location_latitude`, `location_longitude` (stored point,
  read back), `start_date`, `end_date`, `start_time`, `end_time`,
  `payment_amount`, `payment_type`, `workers_required`,
  `application_deadline`, `eligibility_notes`, `status`, `created_at`,
  `updated_at`.
- `category_id` and `required_skill_ids` are write-only.
  `location_latitude`/`location_longitude` are **read-write**: supplied on
  input, echoed on output from the stored PostGIS point.

### `PATCH/PUT /api/v1/jobs/jobs/{id}/` — edit

- **Business role only**, own jobs only (another business's job → `404`).
- While the job is in `DRAFT`, every field is editable.
- After publication, the fields that define the deal are protected against
  **changes**: `title`, `category`, `job_type`, `payment_type`,
  `payment_amount`, `start_date`, `end_date`, and location. The check is
  value-based — a protected field may be resubmitted with its unchanged
  value (clients that PATCH full objects are fine), but a genuinely changed
  value is rejected with `400` (`"<field> is protected after publication."`).
  Changed coordinates submitted via `location_latitude`/`location_longitude`
  are caught by the same check. Two controlled exceptions:
  - `application_deadline` may only be **extended**, never pulled earlier
    (`"application_deadline may only be extended after publication."`).
  - `workers_required` may only **increase**, never shrink
    (`"workers_required may only increase after publication."`).
- `description` and `eligibility_notes` remain editable at any status.

```json
// PATCH /api/v1/jobs/jobs/{id}/ on a PUBLISHED job
{ "title": "New Title" }
// 400
{ "success": false, "data": null, "error": { "code": 400,
  "message": "Validation failed.",
  "details": { "title": ["title is protected after publication."] } } }
```

### `DELETE /api/v1/jobs/jobs/{id}/`

- **Business role only**, own jobs only (→ `404` otherwise). Hard delete.
- **Warning:** deleting a job permanently deletes every application on it —
  `Application.job` is `on_delete=CASCADE` (`apps/applications/models.py`),
  so Phase 7 application rows are removed silently, with no confirmation
  and no restore. Prefer `close`/`cancel` for any job with history.

## Lifecycle

Transitions form a small state machine: `DRAFT → PUBLISHED → OPEN/FULL →
CLOSED`, with `CANCELLED`/`EXPIRED` terminal. `EXPIRED` exists in the model
but no Phase 5 endpoint sets it. All four actions are `POST` and return the
updated job on success (`200` with the full job JSON). Their error
responses are hand-built in the view — exact messages below.

- **Two distinct `403` paths:** a non-business caller (e.g. a student) is
  rejected by the `IsBusiness` permission class with `"This action is only
  available to business accounts."` before the view runs; a **business
  non-owner** instead receives the per-action hand-built message
  (`"You do not have permission to publish/close/cancel/reopen this job."`).
- `publish` has a third `403` path: an **unverified business owner** is
  rejected by `IsVerified` with `"Your account must be verified to perform
  this action."`
- The model also defines a `transition_to()` map that these endpoints do
  **not** call — the views enforce their own inline status sets, which
  currently match the model's map exactly. If one changes without the
  other, the per-action status lists below (view behavior) are
  authoritative.

### `POST /api/v1/jobs/jobs/{id}/publish/`

- Owner of the job only. `DRAFT → PUBLISHED`; rejects with `400` if the job
  is not a draft or fails `is_publish_ready()` (title, description,
  eligibility_notes non-blank, category/location/dates/payment all set).
- **Verified businesses only** (`IsVerified`): an unverified business owner
  gets `403` with `"Your account must be verified to perform this action."`.
  The flag is earned through the Phase 9 verification workflow (submit →
  admin `UNDER_REVIEW` → admin `VERIFIED`); see `docs/PHASE9_API.md`.

```json
// 200 (truncated)
{ "id": "b3a1...", "status": "PUBLISHED", "...": "..." }
// 403 — not the owner (hand-built)
{ "success": false, "data": null, "error": { "code": 403,
  "message": "You do not have permission to publish this job.",
  "details": null } }
// 400 — wrong status (hand-built)
{ "error": { "code": 400, "message": "Only draft jobs can be published.",
  "details": null }, "success": false, "data": null }
// 400 — incomplete draft (hand-built)
{ "error": { "code": 400,
  "message": "This job is incomplete and cannot be published.",
  "details": null }, "success": false, "data": null }
```

### `POST /api/v1/jobs/jobs/{id}/close/`

- Owner only. `PUBLISHED`/`OPEN`/`FULL → CLOSED`; anything else → `400`
  (`"Only published/open/full jobs can be closed."`, hand-built; 403
  message: `"You do not have permission to close this job."`).

### `POST /api/v1/jobs/jobs/{id}/reopen/`

- Owner only. `CLOSED`/`FULL → OPEN`; anything else → `400`
  (`"Only closed or full jobs can be reopened."`, hand-built; 403 message:
  `"You do not have permission to reopen this job."`).

### `POST /api/v1/jobs/jobs/{id}/cancel/`

- Owner only. Any non-terminal status → `CANCELLED`; `CANCELLED`/`EXPIRED`
  → `400` (`"This job cannot be cancelled from its current status."`,
  hand-built; 403 message:
  `"You do not have permission to cancel this job."`). Every student with
  an application on the job receives a `JOB_CANCELLED` notification (Phase 7
  notification center).

## Discovery (campus-based, PostGIS)

### `GET /api/v1/jobs/jobs/nearby/`

- **Student role only** (`403` for any other role).
- Returns `PUBLISHED`/`OPEN` jobs within `radius_km` (default
  `settings.DEFAULT_DISCOVERY_RADIUS_KM`, currently `20`) of a reference
  campus, using a PostGIS geography distance lookup
  (`location__distance_lte=(point, D(km=radius_km))`), annotated with
  job-to-campus distance and ordered nearest-first. Paginated (20/page).
- Reference campus: `?campus_id=<UUID>` (must be active) wins; otherwise the
  student's own `student_profile.campus`. **A campus is required**: with
  neither, the endpoint returns `400`
  (`"A campus_id is required or a campus must be set on your student
  profile."`) — it no longer falls back to listing all jobs.
- Query params: `campus_id`, `radius_km`. `radius_km` must be a positive
  number: non-numeric → `400` (`"radius_km must be a number."`); zero or
  negative → `400` (`"radius_km must be positive."`).
- The distance annotation is used only for ordering — the response carries
  the standard job fields (see the detail section) and does not include a
  distance value.

```json
// GET /api/v1/jobs/jobs/nearby/?radius_km=5
{
  "count": 1, "next": null, "previous": null,
  "results": [ { "id": "b3a1...", "title": "Nearby Gig", "status": "OPEN",
                 "...": "..." } ]
}
// 400 — no campus_id and no campus on the student profile (hand-built)
{ "success": false, "data": null, "error": { "code": 400,
  "message": "A campus_id is required or a campus must be set on your student profile.",
  "details": null } }
// 403 — non-student (hand-built)
{ "success": false, "data": null, "error": { "code": 403,
  "message": "Only students may access nearby jobs.", "details": null } }
// 401 — unauthenticated (hand-built)
{ "success": false, "data": null, "error": { "code": 401,
  "message": "Authentication required.", "details": null } }
```

### `?sort=distance` on the jobs list

- Same PostGIS distance annotation, available to any authenticated role.
- Origin: `?campus_id` first, then the caller's student or business profile
  campus. **A campus is required**: with neither, the list returns `400`
  (`"A campus_id is required or a campus must be set on your profile to
  sort by distance."`) instead of a 500.

## Role/permission summary

| Endpoint | Student | Business | Admin |
|---|---|---|---|
| `GET` categories | ✅ | ✅ | ✅ |
| Write categories | ❌ | ❌ | ✅ (staff flag) |
| `POST` jobs (create) | ❌ | ✅ | ❌ |
| `GET` jobs list/detail | ✅ (published/open only) | ✅ (own only) | ✅ (all) |
| `PATCH/PUT/DELETE` jobs | ❌ | ✅ (own only) | ❌ |
| `publish` | ❌ | ✅ (own + verified) | ❌ |
| `close/reopen/cancel` | ❌ | ✅ (own only) | ❌ |
| `jobs/nearby/` | ✅ | ❌ | ❌ |

All role checks reuse `apps.accounts.permissions` (`IsBusiness`) plus
queryset scoping — no per-app role logic was reimplemented. Note:
`IsBusinessOwnerOrAdmin` (apps/jobs/permissions.py) is currently
unreachable — the viewset's `get_permissions` overrides the class default
for every action, and the inline admin bypass inside the lifecycle actions
is therefore unreachable too (admins are rejected by `IsBusiness` first).
The table above reflects what actually executes.

## Known gaps / to-fix

**None currently open.** Everything tracked in earlier revisions of this
file has been resolved in code and is documented in its section above:
in-use category delete returns `409`; the protected-field check is
value-based; nearby without a campus returns `400`; `?sort=distance`
without a campus returns `400`; `radius_km` is validated as a positive
number; job responses echo the stored coordinates; publishing requires a
verified business.
