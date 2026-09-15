"""
Development settings. Loaded by default (manage.py defaults to this
module). Optimized for local iteration, not security.
"""

from .base import *  # noqa: F401,F403

DEBUG = True
ALLOWED_HOSTS = ["*"]
