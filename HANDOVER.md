# CampusGig — Platform Handover Document

**Date:** 2026-09-17 · **Branch:** `main` · **HEAD:** `b358b71` (taken-down notice) · Audit originally executed at `98650f8`, refreshed through the F6 series
**Audit scope:** full read-only end-to-end quality audit of backend (Phases 1–13) and frontend (F1–F5), with live verification runs.

---

## 1. Executive summary

CampusGig is a campus jobs marketplace: businesses post part-time gigs near campuses, students discover them within 20 km of their campus, apply, chat, interview, and get hired. The platform ships with trust & safety (business verification, reports, trust scores, risk assessments), role-scoped analytics, an immutable audit trail, and a production-ready Docker deployment.

| Layer | State |
|---|---|
| Backend API (Django 5 + DRF + GeoDjango + PostGIS, Celery, Channels) | **Complete — Phases 1–13** |
| Frontend SPA (React 19 + TypeScript + Vite + React Query + axios) | **Complete — F1–F6** |
| Deployment (Docker Compose, CI, prod settings) | **Complete — Phase 13** |
| Backend tests | **232/232 passing** (205 at audit + 7 F6 serializer + 20 F6 polish/visibility tests) |
| Frontend typecheck + production build | **Clean** (verified this audit; 432 kB JS / 129 kB gzip) |

Git history (oldest → newest): `bbae32e` 9A verification lifecycle → `a651c1a` 9B analytics & audit → `dd3363e` F1 → `59e9c48` F2 → `df71eab` F3 → `96f4503` F4 → `b43a054` F5 → `98650f8` Phase 13 → `a198541` Vite proxy env override → `d71f630` F6 Reviews UI → `1ff7b92` handover refresh → `882ecbe` F6 polish (interview times, report takedown, review moderation) → `f89a9a4` student report button → `b358b71` taken-down notice. Working tree is clean except the intentionally untracked `backend/smoke_test_phase9b.py` and `.freebuff/` (local agent run notes).

---

## 2. Audit verification results (executed for this document)

| Check | Command | Result |
|---|---|---|
| Backend dev check | `manage.py check` | 0 issues |
| Migrations in sync | `manage.py makemigrations --check --dry-run` | No changes detected |
| Prod settings load | `manage.py check --settings=config.settings.prod` (with required env) | 0 issues |
| Django deploy check | `manage.py check --deploy --settings=config.settings.prod` | Only pre-existing cosmetic drf-spectacular warnings (serializer type-hints, enum-name collisions, 5 APIViews without serializer_class) + expected W009 from the short audit secret. **No security findings.** |
| Backend test suite | `pytest apps/…` (all 11 apps) | **232 passing, 0 failed** (jobs + safety suites re-run after the taken-down notice; full suite re-verified after F6 polish, two chunks ~11 min) |
| Frontend typecheck + build | `npm run build` (runs `tsc -b && vite build`) | Clean after F6 polish: 173 modules, `dist/assets/index-*.js` 441.26 kB (gzip 130.58 kB), CSS 16.91 kB |
| Dead-code scan | grep for TODO/FIXME/XXX/HACK across backend + frontend | **None found** |
| Repo hygiene | `git status` | Clean; no junk (caches/venv/logs/`.env`) tracked; smoke script untracked as intended |

Not executable in this environment: `docker compose up --build` live smoke (Docker not installed here). Compose YAML is structurally valid and all referenced paths exist; the 8-point live checklist is in `backend/docs/PHASE13_DEPLOY.md`.

---

## 3. Repository layout & stack

```
campusgig_phase4_fixed/
├── .env.example                  # Root compose contract (Phase 13)
├── .github/workflows/ci.yml     # Backend + frontend CI
├── docker-compose.yml           # db (PostGIS) · redis · api (Daphne) · worker · beat · frontend (nginx)
├── backend/
│   ├── apps/                    # 11 Django apps (see §4)
│   ├── config/                  # settings: base / dev / prod · urls.py · celery · asgi · wsgi
│   ├── deploy/entrypoint.sh     # wait-for-db → migrate → collectstatic → superuser → daphne|gunicorn
│   ├── docs/                    # PHASE4–PHASE13 API & deploy docs
│   ├── requirements/            # base.txt (+ gunicorn, whitenoise), dev.txt
│   ├── Dockerfile · .dockerignore · .env.example
│   └── venv/                    # local Windows venv (untracked)
└── frontend/
    ├── src/
    │   ├── api/                 # 13 typed API modules + client.ts (axios, JWT refresh, session-expiry event)
    │   ├── auth/                # AuthContext (localStorage session), RoleRoute guards
    │   ├── components/          # layout (AppShell, NotificationBell), jobs (Card/Filters/Badge), reviews (ReviewForm, ReviewsList), ui
    │   └── pages/               # student/ business/ admin/ shared/ + auth pages
    ├── Dockerfile · nginx.conf · .dockerignore · vite.config.ts
    └── package.json             # react 19, react-router 7, @tanstack/react-query 5, axios, vite 8, ts 6, oxlint
```

---

## 4. Backend architecture

**11 apps under `backend/apps/`:**

| App | Responsibility |
|---|---|
| `accounts` | Custom User (email login, `student`/`business`/`admin` roles, `is_verified`), JWT register/login/refresh/logout/me |
| `profiles` | Student/Business profiles, campuses (PostGIS points), skills, availability, student completion %, student discovery |
| `jobs` | JobCategory + Job CRUD, lifecycle (draft→published→closed/cancelled→reopened), verified-business publish gate, PostGIS 20 km nearby discovery, filters/sort (incl. distance) |
| `applications` | Apply/withdraw, duplicate prevention, pipeline SUBMITTED→SHORTLISTED→INTERVIEW→SELECTED/REJECTED, role-scoped student/business views |
| `matching` | Recommendations with score breakdown (skills/location/availability), preferences, engagements (view/save/click) |
| `communication` | Conversations + messages (REST), chat-eligibility (SELECTED/INTERVIEW-stage apps), read receipts; **Channels WebSocket consumer + JWT auth middleware exist and are tested** |
| `interviews` | Scheduling from INTERVIEW-stage applications, role-aware status transitions (student: confirm/decline; business: cancel; either: complete; terminal states immutable) — 10 dedicated tests |
| `notifications` | In-app notifications, unread count, mark-read; Celery email tasks + beat schedule (deadline reminders) |
| `safety` | BusinessVerification (SUBMITTED→UNDER_REVIEW→VERIFIED/REJECTED + revoke/resubmit, **no fast-track**), VerificationHistory, reports + admin review (**actioning a JOB report cancels the job** — F6 takedown, once per report, owner notified), reviews (peer ratings, **admin hide/restore via /safety/admin/reviews/**), trust scores, risk assessments |
| `core` | Health check, immutable AuditLog (actor/action/target/metadata, admin-only, IP + user-agent metadata), three role-scoped analytics endpoints |
| `cross-cutting` | `IsAdminRole`/`IsBusiness`/`IsStudent` permission classes, explicit `AuditService.log()` calls at audit-relevant call sites (no signals), throttled auth endpoints |

**Settings:** `base.py` (env-driven via django-environ; JWT lifetimes, auth throttle, pagination, drf-spectacular schema/docs) · `dev.py` (SQLite-safe local defaults, console email) · `prod.py` (secrets all env-required: SECRET_KEY, ALLOWED_HOSTS, DB creds; whitenoise `CompressedManifestStaticFilesStorage`; `SECURE_PROXY_SSL_HEADER`; env CORS/CSRF; SMTP from env; `CELERY_TASK_ALWAYS_EAGER=False`; structured console logging; HSTS/SSL/nosniff/referrer flags).

**Auth flow:** JWT pair (access + refresh, rotation on refresh), refresh blacklisted on logout (205), `/auth/me/` for session restore. Roles enforced server-side by permission classes and per-view role checks; the audit's permission tests cover cross-role denial.

---

## 5. Complete API surface (`/api/v1/…`)

- **Auth** (`/auth/`): `register/`, `login/`, `token/refresh/`, `token/verify/`, `logout/`, `me/`
- **Profiles** (`/profiles/`): `students/me/` (+`/skills/`, `/availability/` with detail routes), `business/me/`, `discover/students/`, router: `campuses/`, `skills/`
- **Jobs** (`/jobs/`): router `jobs/` (list/detail CRUD + `publish`/`close`/`cancel`/`reopen` actions, `nearby/`, filters incl. `sort=distance`) and `categories/`
- **Applications** (`/applications/`): `student/` list+create, `student/<uuid>/`, `student/<uuid>/withdraw/`, `business/`, `business/<uuid>/` (PATCH status transitions)
- **Matching** (`/matching/`): `recommendations/`, `matches/`, `matches/calculate/<job_id>/`, `preferences/`, `engagements/` (+detail)
- **Communication** (`/communication/`): `conversations/` (+detail), `conversations/<id>/messages/`, `messages/<uuid>/read/`
- **Interviews** (`/interviews/`): `` list+create, `<uuid>/` detail (PATCH transitions)
- **Notifications** (`/notifications/`): `` list (with unread count), `<uuid>/read/`
- **Safety** (`/safety/`): `verification/` (business submit/resubmit), `admin/verifications/` (+`<uuid>/review/`, `/revoke/`), `reports/` (+detail, `admin/reports/<uuid>/review/`), `reviews/<user_id>/`, `trust/me/`, `admin/risk/<pk>/`, `admin/risk/jobs/<job_id>/calculate/`
- **Core** (mounted directly): `health/`, `audit/logs/` (admin-only, filters + pagination), `analytics/admin/`, `analytics/business/me/`, `analytics/student/me/`
- **Docs:** `api/v1/docs/` (Swagger), `api/v1/redoc/`, `api/v1/schema/`

**Frontend ↔ backend parity:** every page consumes these real endpoints through the typed modules in `frontend/src/api/` — no mocked data anywhere in the app.

---

## 6. Frontend surface

**Stack:** React 19, TypeScript (strict, `tsc -b` project refs), Vite 8, React Router 7, React Query 5, axios (single `client.ts`: attaches access token, rotates refresh on 401, dispatches `cg:session-expired` to reset auth), oxlint.

**Auth & routing:** `/login`, `/register`; session persisted (`cg.access`/`cg.refresh`/`cg.user`); `ProtectedRoute` + per-role `RoleRoute` guards redirect unauthorized roles to their own home (verified live: student at `/admin` → bounced to `/student`).

| Role | Pages |
|---|---|
| **Student** | Dashboard (+ reviews about you), Job discovery (campus-based, filters, sort incl. distance), Job detail (coordinates echo, engagement tracking, business reviews, apply), My applications (withdraw, leave review), Recommendations (score breakdown, save/engage), Profile editor (skills/availability) |
| **Business** | Dashboard (analytics + reviews about your business), My jobs, Job editor (CRUD + publish/close/cancel/reopen), Applicants (pipeline transitions, chat, leave review), Verification wizard (submit/resubmit), Business profile editor |
| **Admin** | Dashboard (real platform analytics: stat cards, date-window + interval, timeseries bars, status breakdowns), Verification review queue (two-step SUBMITTED→UNDER_REVIEW→VERIFIED/REJECTED, revoke with notes, re-verify), Audit-log viewer (action/target/actor/date filters + pagination), Report moderation (take review → valid/dismissed/actioned with notes; actioning a JOB report takes the job down), Review moderation (`/admin/reviews` — hide/restore with required notes) |
| **Shared** | Messages (two-pane threads, 5s polling, auto-mark-read), Interviews (role-aware schedule/confirm/decline/cancel/complete), Notifications (page + topbar bell with unread count), Reviews (`/reviews/:userId` — full review history for any account) |

**F6 reviews (new):** once a job is CLOSED/EXPIRED, both parties of a SELECTED application can rate each other 1–5 with an optional comment — students from My applications, businesses from Applicants (inline star form; the row flips to "You rated ★…" and duplicates are blocked server-side). Received reviews with averages render on both dashboards, on the student job-detail page ("About the business"), and in full on `/reviews/:userId`. The client gates the button from new serializer fields (`job_status`, `counterparty_id`, `my_review_rating`, `business_user_id`) while the Phase 8 rules remain the enforcement point; the business dashboard's "Average rating" stat is now fed by live reviews through the 9B trust score. Covered by `backend/apps/applications/tests/test_f6_review_serializer_fields.py` (7 tests).

**Design:** single custom CSS design system in `index.css` (no UI framework), responsive at mobile widths, consistent error/empty/loading states via shared components.

---

## 7. Testing & CI

- **Backend:** 232 tests across 22 files — models, permissions, views, serializers, regressions (application validation, interview transitions), health, analytics, audit, phases 7/8/9, F6 review-serializer contracts, and F6 polish (interview-time formatting, report takedown incl. idempotency/dangling-target/notification-failure cases, review moderation incl. audit trail, duplicate-report suppression, history-scoped job visibility + viewer_has_history). Suite takes ~11 min on the dev machine (heavy PostGIS/point setup dominates).
- **Frontend:** verification is `tsc -b` + production build + live E2E (per-phase manual E2E was performed through F1–F6 in the running app: F6 reviews across both roles, and the F6 polish + trust loop — review hide/restore in `/admin/reviews`, report actioning with live job takedown, humanized interview notification, student report submission from the job page, and the taken-down banner on a cancelled job). No JS unit-test framework is installed (deliberate — consistent with F1–F5; see §11).
- **CI** (`.github/workflows/ci.yml`): backend job — PostGIS + Redis service containers, GeoDjango system libs, dev requirements, `manage.py check` + prod-settings check + full pytest; frontend job — `npm ci`, `tsc -b`, build. Not yet exercised (no remote with Actions configured).

---

## 8. Local development quickstart

```bash
# Backend (Windows, as used on this machine)
cd backend
python -m venv venv && venv\Scripts\activate
pip install -r requirements/dev.txt
copy .env.example .env            # fill DB creds (PostGIS 16-3.4 expected)
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver        # → http://127.0.0.1:8000

# Frontend (separate shell)
cd frontend
npm ci
npm run dev                       # → http://localhost:5173 (proxies /api → :8000)
```

Redis is required for Celery/Channels behaviour in dev (docker-compose provides one; without it, channel layer falls back to in-memory per `CHANNEL_LAYER_BACKEND`).

---

## 9. Deployment (Phase 13)

Full runbook: **`backend/docs/PHASE13_DEPLOY.md`** (prerequisites, env setup, migrations, superuser bootstrap, compose startup, access URLs, worker/beat verification, production checklist, troubleshooting).

```bash
cp .env.example .env     # set SECRET_KEY, DJANGO_SUPERUSER_*, CORS if exposing API separately
docker compose up --build
```

- **api** → Daphne (ASGI) by default (`SERVER_KIND=asgi`) — preserves the Channels WebSocket architecture; `SERVER_KIND=wsgi` selects gunicorn for HTTP-only replicas.
- **frontend** → nginx: SPA fallback, immutable asset caching, `/api` proxy to `api:8000` with WebSocket upgrade headers (same-origin ⇒ CORS normally empty).
- **entrypoint** waits for db, migrates, collectstatics, bootstraps the initial superuser from `DJANGO_SUPERUSER_EMAIL`/`_PASSWORD`, then serves.
- **prod settings** require `SECRET_KEY`, `ALLOWED_HOSTS`, and DB creds from env (no insecure fallbacks); whitenoise verified via `collectstatic` (170 → 490 files).

---

## 10. Known issues & limitations (honest list)

**Minor functional gaps:**
1. ~~**Reviews have no UI**~~ **Closed in F6** (`d71f630` + `882ecbe`) — reviews are written from My applications / Applicants after a completed engagement, displayed on dashboards, job detail, and `/reviews/:userId`, and admins hide/restore them from `/admin/reviews` (audited). No remaining gap.
2. **Chat uses 5s REST polling** — the tested WebSocket consumer is not yet used by the frontend (documented in `Messages.tsx`). Works fine at current scale; WS adoption is a deliberate follow-up.
3. ~~**Interview notification bodies show raw ISO timestamps**~~ **Closed in F6 polish** (`882ecbe`) — bodies now read "18 Sep 2026, 09:12 IST" in the interview's timezone (invalid zones fall back to `TIME_ZONE`).
4. ~~**Report "ACTIONED" is bookkeeping only**~~ **Closed in F6 polish + notice** (`882ecbe`, `b358b71`) — actioning a JOB report cancels the job from discovery and notifies the owner, once per report (re-reviews never re-cancel; dangling targets and notifier failures are handled); students who applied to or engaged with the job keep access to its detail page and see a taken-down explanation instead of a 404. No remaining gap.
5. ~~**Student reporting is API-only**~~ **Closed in F6** (`f89a9a4`) — students report a listing from the job detail page (category + description, confidential), with an "already reported" state; a second open report on the same target is rejected server-side while resolved reports never block re-reporting.
6. **In-use JobCategory DELETE surfaces ProtectedError as 500** (pre-existing, known from Phase 5 audit; presence-based protected-field check also documented in `docs/PHASE5_API.md` Known gaps).
7. **`nearby` `radius_km`** is validated for type/positivity but not for an upper bound.

**Environmental / process:**
8. **Docker not available on the dev machine** — container images were validated structurally (compose YAML, Dockerfile stages, POSIX entrypoint, imports); the first real `docker compose up --build` smoke is pending on a Docker host (checklist ready).
9. **CI unexercised** — workflow is written but the repo has no remote with Actions enabled yet.
10. **Media storage** — verification evidence is URL-based; no S3/object-storage integration.
11. **Email** defaults to console backend unless SMTP env vars are provided (intentional; documented).

---

## 11. Recommended roadmap (do NOT treat as committed scope)

**Next features (in suggested order):**
1. **WebSocket chat adoption** in `Messages.tsx` (backend already tested).
2. **Frontend unit tests** (Vitest for `client.ts` refresh logic + auth context), wired into CI.
3. **Live Docker smoke** on a Docker host; then push repo to enable CI.

**Explicitly out of scope for now (per prior decisions):** payments/escrow, email-verification flows, mobile apps, multi-language, notification push channels, multi-tenancy.

*(F6 roadmap note: the entire F6 list shipped across `d71f630`, `882ecbe`, `f89a9a4`, and `b358b71` — reviews read/write, humanized interview times, report-driven takedown with admin moderation, the student report button, and the taken-down notice. The trust loop is fully UI-driven end to end.)*

---

## 12. New-developer checklist

- [ ] Read `backend/docs/PHASE4_API.md` → `PHASE13_DEPLOY.md` (each phase documents endpoints, permissions, validation, known gaps)
- [ ] Interactive docs: run the backend and open `http://127.0.0.1:8000/api/v1/docs/`
- [ ] Run the backend suite before/after any change: `pytest apps -q` (expect 232 passing)
- [ ] Frontend: `npm run build` must stay green; `oxlint` available via `npm run lint`
- [ ] Never edit generated migrations by hand; `makemigrations --check` must stay clean in CI
- [ ] Secrets only via `.env` (root for compose, `backend/.env` for local dev) — templates provided, real `.env` files are git-ignored
- [ ] Audit-relevant state changes must go through `AuditService.log()` (search `apps/core` for the service and existing call sites)
- [ ] Respect the no-fast-track verification lifecycle and role-aware interview transitions (both are test-enforced)
