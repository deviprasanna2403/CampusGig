"""
Production settings (Phase 13 completes the hardening promised here).

Every value that must not silently fall back to an insecure default is
required from the environment (no `default=` kwarg): SECRET_KEY,
ALLOWED_HOSTS, database credentials, CORS origins, and the initial
Django admin password hook (DJANGO_SUPERUSER_PASSWORD) used by the
compose entrypoint.

Serving model: ASGI under Daphne (the Channels-native server, already a
dependency) so the existing WebSocket architecture — JWT middleware +
chat consumer — keeps working in production. Whitenoise serves static
assets. Gunicorn/WSGI remains available as an explicit fallback
(SERVER_KIND=wsgi) for HTTP-only replica setups.
"""

from .base import *  # noqa: F401,F403
from .base import env

DEBUG = False

SECRET_KEY = env("SECRET_KEY")
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS")

SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30  # 30 days
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"

# --- Proxy awareness ---------------------------------------------------------
# Behind the nginx frontend container (or any reverse proxy) Django must trust
# X-Forwarded-For/-Proto or SSLRedirect and client IPs (throttling, audit
# metadata) would be wrong. Private networks only, per Django docs.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# --- Static files (whitenoise) ------------------------------------------------
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# --- CORS / CSRF --------------------------------------------------------------
# In production the browser talks to the API through the nginx proxy on the
# same origin, so CORS is normally empty. Deployments that expose the API on
# its own domain set CORS_ALLOWED_ORIGINS explicitly (comma-separated).
CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=[])
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])

# --- Email ---------------------------------------------------------------------
# Real SMTP in production; credentials come from the environment. The console
# backend in base.py remains the development default.
EMAIL_BACKEND = env(
    "EMAIL_BACKEND",
    default="django.core.mail.backends.smtp.EmailBackend",
)
# Empty host is fine under the console backend; required by the SMTP one.
EMAIL_HOST = env("EMAIL_HOST", default="")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)

# --- Background jobs -------------------------------------------------------------
# Never run Celery tasks inline in production: a broker hiccup must not tie up
# web workers, and beat must be the single scheduler.
CELERY_TASK_ALWAYS_EAGER = False

# --- Logging -----------------------------------------------------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "plain": {"format": "%(asctime)s %(levelname)s %(name)s %(message)s"},
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "plain",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": env("LOG_LEVEL", default="INFO"),
    },
    "loggers": {
        "django": {"level": "INFO"},
        # Surface blocked requests (suspicious hosts, disallowed redirects).
        "django.security": {"level": "WARNING"},
        # DRF logs the request line on API errors; keep it visible but quiet.
        "django.request": {"level": "WARNING"},
    },
}
