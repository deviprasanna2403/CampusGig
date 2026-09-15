# Phase 4 API — Profiles, Campus, Skills, Availability, Discovery

Interactive, always-up-to-date docs are already served by drf-spectacular
(installed in Phase 3, unchanged here):

- Swagger UI: `GET /api/v1/docs/`
- ReDoc: `GET /api/v1/redoc/`
- Raw OpenAPI schema: `GET /api/v1/schema/`

This file is a human-readable summary of what Phase 4 adds on top of that.
All endpoints below live under `/api/v1/profiles/` and require
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

## Reference data

### `GET/POST /api/v1/profiles/campuses/`, `GET/PATCH/DELETE /api/v1/profiles/campuses/{id}/`

- Read (list/retrieve): any authenticated role.
- Write (create/update/delete): **admin role only**. `DELETE` soft-deactivates
  (`is_active=False`) rather than hard-deleting, so existing student/business
  profiles pointing at a campus never get orphaned by `on_delete=PROTECT`.
- Body fields: `name`, `city`, `state`, `country`, `latitude`, `longitude`
  (decimal degrees, WGS84; validated to `[-90, 90]` / `[-180, 180]`),
  `is_active`.
- `latitude`/`longitude` are a convenience wrapper around a PostGIS
  `PointField(geography=True, srid=4326)` — the client never sees WKT/GeoJSON.
- Query params: `?city=<exact, case-insensitive>`.

### `GET/POST /api/v1/profiles/skills/`, `GET/PATCH/DELETE /api/v1/profiles/skills/{id}/`

- Same read/write split as Campus (admin-only write).
- Fields: `name` (unique, case-insensitive), `category`, `is_active`.
- Query params: `?category=<exact, case-insensitive>`.

## Student profile

### `GET/PATCH /api/v1/profiles/students/me/`

- **Student role only.** The profile row is created automatically
  (`get_or_create`) the first time this is called for a given user — there
  is no separate "create profile" step.
- Fields: `full_name`, `campus` (nested, read-only) / `campus_id` (write,
  FK to an active Campus), `year_of_study` (1–6), `bio`, `resume_headline`,
  `skills` (nested, read-only — see below to add/remove), `availability`
  (nested, read-only — see below to add/remove), `completion_percentage`
  (0–100, computed), `is_complete` (bool, computed). `email`/`id` read-only.
- **Profile completion** is computed from four checks — `full_name` set,
  `campus` set, at least one skill added, at least one availability slot
  added — each worth 25%. It is never stored, so it can't drift from the
  underlying data.

### `GET/POST /api/v1/profiles/students/me/skills/`, `GET/DELETE /api/v1/profiles/students/me/skills/{id}/`

- **Student role only**, scoped to the caller's own rows (the queryset
  filters by `student__user=request.user`, not just the permission class —
  a student cannot delete another student's skill row even by guessing its
  UUID: it 404s, not 403s, to avoid confirming the row exists).
- `POST` body: `skill_id` (UUID), `proficiency`
  (`beginner`/`intermediate`/`advanced`/`expert`), `years_of_experience`
  (optional, 0–50).
- Adding a skill already on the profile returns `400` with a field error on
  `skill_id`.

### `GET/POST /api/v1/profiles/students/me/availability/`, `GET/PATCH/PUT/DELETE /api/v1/profiles/students/me/availability/{id}/`

- **Student role only**, same self-scoping as skills.
- Body: `day_of_week` (0=Monday … 6=Sunday), `start_time`, `end_time`
  (`HH:MM:SS`), `is_active`.
- Rejected with `400` if `end_time <= start_time`, or if the slot overlaps
  an existing slot on the same day for the same student. Enforced at both
  the serializer layer (clear error message) and the database layer (a
  `CheckConstraint` on `end_time > start_time`, so no code path — including
  a future bulk import — can write invalid rows).

## Business profile

### `GET/PATCH /api/v1/profiles/business/me/`

- **Business role only.** Same lazy-creation pattern as the student profile.
- Fields: `business_name`, `description`, `website`, `industry`, `campus`
  (nested, read-only) / `campus_id` (write) — this is the business's
  *default* reference campus for discovery searches below —
  `completion_percentage`, `is_complete`.

## Discovery (campus-based, PostGIS)

### `GET /api/v1/profiles/discover/students/`

- **Business role only.**
- Finds every active `Campus` within `radius_km` (default
  `settings.DEFAULT_DISCOVERY_RADIUS_KM`, currently `20`) of a reference
  campus, using a PostGIS geography distance lookup
  (`location__distance_lte=(point, D(km=radius_km))`), then returns the
  `StudentProfile`s registered at those campuses, annotated with the
  campus-to-campus distance and ordered nearest-first. Paginated (project
  default: 20/page).
- **Never** filters or ranks by an individual student's location — no such
  field exists on `StudentProfile`. A student's exact position is never
  collected, stored, or exposed; only their registered campus is.
- The response fields are deliberately narrower than the student's own
  profile view: `id`, `full_name`, `resume_headline`, `year_of_study`,
  `campus_name`, `campus_city`, `distance_km`, `skills` (list of names).
  No `email`, no `phone`, no raw campus coordinates.
- Query params:
  - `campus_id` (optional UUID) — reference point. Defaults to the
    business's own `business_profile.campus`. `400` if neither is set.
  - `radius_km` (optional, `1`–`100`) — overrides the default 20 km.
  - `skill` (optional) — case-insensitive exact match on skill name.
- This endpoint is intentionally the only Phase 4 consumer of
  `DEFAULT_DISCOVERY_RADIUS_KM`; the Jobs phase (Phase 5) will reuse the
  same setting and the same "campus radius → students at those campuses"
  query pattern for job-to-student matching, not implemented here.

## Role/permission summary

| Endpoint | Student | Business | Admin |
|---|---|---|---|
| `GET` campuses/skills | ✅ | ✅ | ✅ |
| Write campuses/skills | ❌ | ❌ | ✅ |
| `students/me/*` | ✅ (own only) | ❌ | ❌ (not a student account) |
| `business/me/` | ❌ | ✅ (own only) | ❌ |
| `discover/students/` | ❌ | ✅ | ❌ |

All permission checks reuse `apps.accounts.permissions` (`IsStudent`,
`IsBusiness`) — no role logic was reimplemented for Phase 4.
