# Phase 13 — Production Readiness & Deployment

This phase completes the deployment promise deferred since Phase 2
(`docker-compose.yml`'s own header) and the hardening deferred by
`config/settings/prod.py` ("full production hardening ... is completed
in Phase 13").

## What ships

| Piece | File | Notes |
|---|---|---|
| Backend image | `backend/Dockerfile` | Multi-stage: wheels built against libpq, slim runtime with GDAL/GEOS/PROJ libs; `collectstatic` at build |
| Entrypoint | `backend/deploy/entrypoint.sh` | Waits for db → `migrate` → `collectstatic` → idempotent superuser → **Daphne/ASGI by default** (gunicorn via `SERVER_KIND=wsgi`) |
| Frontend image | `frontend/Dockerfile` | `npm ci && npm run build` → nginx:alpine |
| nginx | `frontend/nginx.conf` | SPA fallback, hashed-asset caching, `/api` proxy (WS-upgrade ready) to `api:8000` |
| Full stack | `docker-compose.yml` | `db` (PostGIS) + `redis` + `api` (Daphne/ASGI) + `worker` (Celery) + `beat` + `frontend` (nginx) |
| Prod settings | `backend/config/settings/prod.py` | Whitenoise, `SECURE_PROXY_SSL_HEADER`, env-driven CORS/CSRF/SMTP, structured logging, `CELERY_TASK_ALWAYS_EAGER=False` |
| CI | `.github/workflows/ci.yml` | Backend: pytest (PostGIS+Redis services) + prod-settings check. Frontend: `tsc -b` + build |

## One-command local stack

```bash
cp .env.example .env          # then edit SECRET_KEY + superuser password
docker compose up --build
```

- Frontend: http://localhost (nginx; SPA + `/api` proxy)
- API directly: http://localhost:8000/api/v1/ — Daphne/ASGI serves Channels
  WebSockets too (`/ws/...`; see `apps/communication/routing.py`)
- Django admin: bootstrap via `DJANGO_SUPERUSER_EMAIL`/`DJANGO_SUPERUSER_PASSWORD`

The API entrypoint runs migrations automatically. To run them manually:
`docker compose exec api python manage.py migrate`.

## Environment variables (root `.env.example`)

Required: `SECRET_KEY` (compose fails fast without it), `DB_PASSWORD`,
`DJANGO_SUPERUSER_*`. Important optional: `ALLOWED_HOSTS`,
`SERVER_KIND` (`asgi` default | `wsgi`), `CORS_ALLOWED_ORIGINS` /
`CSRF_TRUSTED_ORIGINS` (only when the API is exposed on its own
domain — same-origin proxying keeps them empty), SMTP settings +
`PHASE7_EMAIL_NOTIFICATIONS=True` for real email.

Backend-only development keeps using `backend/.env` with
`config.settings.dev` as before — nothing about the dev flow changed.

## Serving model

Production serves **ASGI via Daphne** — the Channels-native server, already
a project dependency — so the existing WebSocket architecture (JWT auth
middleware + chat consumer, tested in Phase 7) works end to end out of the
box. Static assets are served by **whitenoise**
(`CompressedManifestStaticFilesStorage`). nginx additionally forwards
WebSocket `Upgrade` headers on `/api`, so the frontend can adopt WS chat
without any deployment change.

Gunicorn/WSGI stays available as an explicit fallback (`SERVER_KIND=wsgi`)
for HTTP-only replica tiers; it is intentionally not the default because a
WSGI-only deployment would silently disable WebSockets.

The current frontend still uses REST polling for chat (unchanged by
request); the WS path is ready whenever the frontend switches.

## Verification checklist

1. `docker compose up --build` — all six services healthy
2. `curl -f http://localhost/api/v1/health/` — `{"status": "ok"}`
3. Register/login through the nginx-served frontend (same-origin; no CORS preflight)
4. Create job → apply → notification appears (worker + beat logs clean)
5. Worker/beat: `docker compose logs worker beat` show Celery ready lines
   (`celery@... ready.` / `beat: Starting...`)
6. WebSocket sanity (asgi default): the chat consumer route accepts an
   authenticated WS handshake
7. `docker compose exec api python manage.py check --deploy` — security warnings triaged
8. CI green on push (backend 205 tests, frontend typecheck+build)

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `compose` refuses to start: "set SECRET_KEY in .env" | Copy `.env.example` → `.env` and fill required values |
| api container restarts in a loop | DB not ready or credentials wrong — check `docker compose logs db api`; the entrypoint waits via `pg_isready` |
| 400 Host header from the API | `ALLOWED_HOSTS` must include the host you browse (defaults include `localhost`, `127.0.0.1`, `api`) |
| CSRF failures when POSTing from another origin | Set `CSRF_TRUSTED_ORIGINS` (scheme included, e.g. `https://campusgig.example`) |
| Static files 404 / manifest errors | Whitenoise manifest is built by `collectstatic` in entrypoint; run `docker compose exec api python manage.py collectstatic` |
| No notification emails | `PHASE7_EMAIL_NOTIFICATIONS` is False or EMAIL_BACKEND is console; set SMTP vars and restart worker |
| WebSocket handshake fails | Ensure `SERVER_KIND=asgi` (default) — under `wsgi` Daphne/Channels are not served |

## Known limitations / next candidates

- Media uploads (verification evidence is stored as URLs, not files) — no
  object storage configured.
- Single-node compose deployment; Kubernetes/TLS termination is
  deployer-owned (HSTS/SSL flags are already set).
- Email uses SMTP directly; a transactional provider integration is a
  future enhancement.
