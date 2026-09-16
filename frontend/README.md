# CampusGig Frontend (React + TypeScript + Vite)

Phase F1: scaffold, API client, JWT auth with rotation-aware refresh, role-based routing.

## Stack

- Vite + React 18 + TypeScript
- React Router 6 (role-scoped routes), TanStack Query (server state)
- Axios client with the backend's error envelope + single-flight 401 refresh
  (SimpleJWT rotates **both** tokens on refresh — the client stores both)

## Development

```bash
npm install
npm run dev        # http://localhost:5173
```

The dev server proxies `/api/*` to `http://127.0.0.1:8000` (Django) — no CORS
involved locally. Start the backend first:

```bash
cd ../backend
./venv/Scripts/python.exe manage.py runserver 127.0.0.1:8000
```

### Environment

Copy `.env.example` to `.env` if you need a non-default API origin
(e.g. pointing at a deployed backend). In dev, leave `VITE_API_BASE_URL` empty.

### Cross-origin deployments

The backend has `django-cors-headers` installed; `dev.py` already allows
`localhost:5173`/`127.0.0.1:5173`. For other origins, extend
`CORS_ALLOWED_ORIGINS` in the relevant settings module.

## Roles & routing

| Route prefix | Role | Notes |
|---|---|---|
| `/login`, `/register` | public | register creates student/business only (backend-enforced) |
| `/student` | student | dashboard lands in Phase F2 |
| `/business` | business | console lands in Phase F3 |
| `/admin` | admin | console lands in Phase F5 |

Login redirects each role to its home (`guards.tsx::homeFor`). Wrong-role
access redirects to the user's own home.

## Sessions

- Access token: 15 min; refresh: 7 days, rotated on every refresh and
  blacklisted on logout (backend config).
- On 401, the client refreshes once (single-flight) and replays the request;
  if refresh fails, the session clears and the user returns to `/login`.
