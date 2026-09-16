"""
Development settings. Loaded by default (manage.py defaults to this
module). Optimized for local iteration, not security.
"""

from .base import *  # noqa: F401,F403

DEBUG = True
ALLOWED_HOSTS = ["*"]

# Vite dev server origin for the React frontend (Phase F1).
CORS_ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]
