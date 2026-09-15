"""
Settings used only for the automated test suite (see pytest.ini's
DJANGO_SETTINGS_MODULE). Inherits everything from dev.py — and, through
it, base.py — except the cache backend.

Why this file exists
---------------------
DRF's ScopedRateThrottle (applied to the `auth` scope: register/login/
refresh/logout — see apps/accounts/views.py's `throttle_scope = "auth"`)
counts requests by storing a per-client hit history in Django's cache
framework. No CACHES setting is defined anywhere in this project, so
Django silently falls back to its implicit default: a single
process-wide LocMemCache.

A full pytest run is one process. That cache — and therefore every
throttle counter in it — is shared for the lifetime of the entire test
session, not reset per test or per test class (unlike the database,
which pytest-django wraps in a transaction per test and rolls back).
Every test that hits register/login/refresh/logout from the same test
client (same IP) adds to the same "auth" scope counter. Once enough of
those accumulate across the session, an unrelated, later test can
receive a stale 429 instead of the status code it's actually testing for
— exactly the failure seen in
apps/accounts/tests/test_views.py::LoginTests::test_login_unknown_email_fails.

The fix: use Django's dummy cache backend for test runs only. Every
`cache.get()` becomes a miss and every `cache.set()` a no-op, so
ScopedRateThrottle always sees an empty history — throttling is
structurally inert for the duration of the test suite, without touching
the throttle classes, rates, or any view/serializer. This is the
standard approach for isolating cache-backed throttles/rate limits in
Django test suites.

This module is never used by `manage.py runserver` (dev.py) or
production (prod.py) — both are completely unaffected, so real request
throttling is exactly as strict in development and production as it was
before this file existed.
"""

from .dev import *  # noqa: F401,F403

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.dummy.DummyCache",
    }
}

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
        "CONFIG": {},
    }
}
