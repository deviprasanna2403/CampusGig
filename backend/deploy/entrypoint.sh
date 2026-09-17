#!/bin/sh
set -e

# Wait for PostgreSQL (compose healthcheck also gates this, but keep the
# entrypoint self-sufficient for non-compose deployments).
until pg_isready -h "${DB_HOST:-db}" -p "${DB_PORT:-5432}" -U "${DB_USER:-campusgig_user}" -q; do
  echo "Waiting for postgres at ${DB_HOST:-db}:${DB_PORT:-5432}..."
  sleep 2
done

python manage.py migrate --noinput

# Static assets are normally baked in at build time; collect again here so the
# manifest exists even if the build-time collect was deferred.
python manage.py collectstatic --noinput

# Bootstrap the initial superuser once (idempotent).
if [ -n "${DJANGO_SUPERUSER_EMAIL:-}" ] && [ -n "${DJANGO_SUPERUSER_PASSWORD:-}" ]; then
  python manage.py shell -c "
from django.contrib.auth import get_user_model
User = get_user_model()
email = '${DJANGO_SUPERUSER_EMAIL}'
if not User.objects.filter(email=email).exists():
    User.objects.create_superuser(email=email, password='${DJANGO_SUPERUSER_PASSWORD}')
    print('superuser created:', email)
else:
    print('superuser already exists:', email)
"
fi

# Default: ASGI via Daphne — the Channels-native server. This preserves the
# existing WebSocket architecture end to end (JWT middleware + chat consumer);
# nothing about the deployment disables WebSockets. Set SERVER_KIND=wsgi to
# run gunicorn instead (e.g. HTTP-only replicas behind a separate ASGI tier).
case "${SERVER_KIND:-asgi}" in
  wsgi)
    exec gunicorn config.wsgi:application \
      --bind 0.0.0.0:8000 \
      --workers "${GUNICORN_WORKERS:-3}" \
      --timeout "${GUNICORN_TIMEOUT:-60}"
    ;;
  *)
    exec daphne -b 0.0.0.0 -p 8000 config.asgi:application
    ;;
esac
