"""
Base settings shared by every environment (dev, prod).

Environment-specific overrides live in dev.py / prod.py. Nothing in this
file should be environment-specific except by way of an environment
variable read through django-environ.
"""

from pathlib import Path

import environ

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
# backend/config/settings/base.py -> parents: settings, config, backend
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# ---------------------------------------------------------------------------
# Environment variables
# ---------------------------------------------------------------------------
env = environ.Env()

# Look for a .env file at backend/.env (one level above config/)
_env_file = BASE_DIR / ".env"
if _env_file.exists():
    environ.Env.read_env(str(_env_file))

# ---------------------------------------------------------------------------
# Core Django
# ---------------------------------------------------------------------------
SECRET_KEY = env("SECRET_KEY", default="unsafe-development-secret-key-change-me")
DEBUG = env.bool("DEBUG", default=False)
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])

INSTALLED_APPS = [
    # F6: serves the Channels WebSocket consumer through `manage.py runserver`
    # (Django switches runserver to ASGI only when daphne is listed here).
    # Must precede django.contrib.staticfiles. Production is unaffected —
    # deploy/entrypoint.sh runs Daphne directly.
    "daphne",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # GeoDjango — required for PostGIS PointFields used from Phase 4 onward.
    "django.contrib.gis",
    # Django REST Framework
    "rest_framework",
    # JWT authentication + refresh-token blacklisting (Phase 3)
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    # OpenAPI/Swagger schema generation (Phase 3)
    "drf_spectacular",
    # CORS for the React frontend (Phase F1) — the Vite dev server proxies
    # /api in development; this matters for cross-origin deployments.
    "corsheaders",
    # CampusGig apps
    "apps.core",
    "apps.accounts",
    # StudentProfile/BusinessProfile/Campus/Skill/StudentSkill/Availability (Phase 4)
    "apps.profiles",
    # Jobs marketplace (Phase 5)
    "apps.jobs",
    # Transparent matching and recommendations (Phase 6)
    "apps.matching",
    # Applications, communication, interviews, and notifications (Phase 7)
    "apps.applications",
    "apps.communication",
    "apps.interviews",
    "apps.notifications",
    "apps.safety",
]

MIDDLEWARE = [
    # django-cors-headers must run before anything that can produce a
    # response (its documented requirement) — handles preflights + headers.
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# ---------------------------------------------------------------------------
# Database — PostgreSQL + PostGIS via GeoDjango's postgis backend
# ---------------------------------------------------------------------------
DATABASES = {
    "default": {
        "ENGINE": "django.contrib.gis.db.backends.postgis",
        "NAME": env("DB_NAME", default="campusgig"),
        "USER": env("DB_USER", default="campusgig_user"),
        "PASSWORD": env("DB_PASSWORD", default="campusgig_password"),
        "HOST": env("DB_HOST", default="localhost"),
        "PORT": env("DB_PORT", default="5432"),
    }
}

# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 8},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ---------------------------------------------------------------------------
# Internationalization
# ---------------------------------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = env("TIME_ZONE", default="Asia/Kolkata")
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# Static & media files
# ---------------------------------------------------------------------------
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# CampusGig domain settings
# ---------------------------------------------------------------------------
# Default radius (km) used for campus-based job discovery.
# See Phase 1 architecture, section 6. First consumed in Phase 5.
DEFAULT_DISCOVERY_RADIUS_KM = env.int("DEFAULT_DISCOVERY_RADIUS_KM", default=20)
# Ceiling for the nearby endpoint's radius_km param: campus jobs are local
# by product definition, and an unbounded radius would make the proximity
# query scan the whole table.
MAX_DISCOVERY_RADIUS_KM = env.int("MAX_DISCOVERY_RADIUS_KM", default=50)

# ---------------------------------------------------------------------------
# GDAL/GEOS overrides
# ---------------------------------------------------------------------------
# GeoDjango auto-detects GDAL/GEOS on Linux (including inside Docker) when
# the system libraries are installed. On some Windows/macOS setups the
# auto-detection fails and these must be set explicitly to the library
# file paths. Leave both unset (None) on Linux/Docker.
GDAL_LIBRARY_PATH = env(
    "GDAL_LIBRARY_PATH",
    default=r"C:\Program Files\PostgreSQL\16\bin\libgdal-35.dll",
)
GEOS_LIBRARY_PATH = env(
    "GEOS_LIBRARY_PATH",
    default=r"C:\Program Files\PostgreSQL\16\bin\libgeos_c.dll",
)

# ---------------------------------------------------------------------------
# Django REST Framework
# ---------------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    # Authenticated-by-default: every new endpoint added in later phases is
    # locked down unless a view explicitly opts into AllowAny (register,
    # login, refresh, and the API docs do this explicitly).
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    # Consistent {"success", "data", "error"} envelope for error responses.
    # See apps/core/exceptions.py.
    "EXCEPTION_HANDLER": "apps.core.exceptions.custom_exception_handler",
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.ScopedRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        # Applied to register/login/refresh/logout to blunt brute-force and
        # account-enumeration attempts (Phase 1, section 18).
        "auth": env("AUTH_THROTTLE_RATE", default="10/min"),
    },
}

ASGI_APPLICATION = "config.asgi.application"

CHANNEL_LAYER_BACKEND = env(
    "CHANNEL_LAYER_BACKEND",
    default="channels.layers.InMemoryChannelLayer",
)
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": CHANNEL_LAYER_BACKEND,
        "CONFIG": (
            {"hosts": [env("REDIS_URL", default="redis://127.0.0.1:6379/1")]}
            if CHANNEL_LAYER_BACKEND == "channels_redis.core.RedisChannelLayer"
            else {}
        ),
    }
}

CELERY_BROKER_URL = env("CELERY_BROKER_URL", default="redis://127.0.0.1:6379/0")
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", default="redis://127.0.0.1:6379/0")
CELERY_TASK_ALWAYS_EAGER = env.bool("CELERY_TASK_ALWAYS_EAGER", default=False)
CELERY_BEAT_SCHEDULE = {
    "send-pending-notification-emails": {
        "task": "apps.notifications.tasks.send_pending_notification_emails",
        "schedule": 60.0,
    },
    "send-job-deadline-reminders": {
        "task": "apps.notifications.tasks.send_job_deadline_reminders",
        "schedule": 3600.0,
    },
}
PHASE7_EMAIL_NOTIFICATIONS = env.bool("PHASE7_EMAIL_NOTIFICATIONS", default=False)
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="notifications@campusgig.local")
EMAIL_BACKEND = env(
    "EMAIL_BACKEND",
    default="django.core.mail.backends.console.EmailBackend",
)

# ---------------------------------------------------------------------------
# Simple JWT
# ---------------------------------------------------------------------------
from datetime import timedelta  # noqa: E402

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(
        minutes=env.int("JWT_ACCESS_TOKEN_LIFETIME_MINUTES", default=15)
    ),
    "REFRESH_TOKEN_LIFETIME": timedelta(
        days=env.int("JWT_REFRESH_TOKEN_LIFETIME_DAYS", default=7)
    ),
    # A refresh call issues a brand-new refresh token and blacklists the old
    # one, so a stolen-but-unused-yet refresh token has a short useful
    # window. Logout blacklists the current refresh token immediately
    # (see apps/accounts/views.py::LogoutView).
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": SECRET_KEY,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
}

# ---------------------------------------------------------------------------
# CORS (React frontend, Phase F1)
# ---------------------------------------------------------------------------
# Deliberately empty in base: production should be same-origin or proxied.
# Environment-specific settings extend CORS_ALLOWED_ORIGINS (see dev.py).
CORS_ALLOWED_ORIGINS = []
CORS_ALLOW_CREDENTIALS = False

# ---------------------------------------------------------------------------
# drf-spectacular (OpenAPI / Swagger)
# ---------------------------------------------------------------------------
SPECTACULAR_SETTINGS = {
    "TITLE": "CampusGig API",
    "DESCRIPTION": "Campus-location-based gig marketplace connecting students and businesses.",
    "VERSION": "0.4.0",
    "SERVE_INCLUDE_SCHEMA": False,
    # Schema/Swagger/Redoc stay publicly viewable even though every other
    # endpoint defaults to IsAuthenticated above.
    "SERVE_PERMISSIONS": ["rest_framework.permissions.AllowAny"],
}
