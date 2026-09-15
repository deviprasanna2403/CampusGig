"""
Shared helpers for profiles app tests. Plain functions, not factory_boy —
factory_boy is listed in requirements/dev.txt but isn't actually used
anywhere in the Phase 1-3 test suite (accounts tests build objects
directly), so Phase 4 tests follow that same convention.
"""

from django.contrib.gis.geos import Point

from apps.accounts.serializers import CustomTokenObtainPairSerializer
from apps.profiles.models import Campus


def bearer_header(user):
    """
    Build an `Authorization: Bearer <access>` value directly from
    `CustomTokenObtainPairSerializer` (the same class RegisterView/LoginView
    use), instead of round-tripping through the login endpoint in every
    test. Avoids adding load to the `auth` throttle scope shared with
    apps.accounts's own tests and is faster (no extra HTTP call/password
    check per test).
    """
    token = CustomTokenObtainPairSerializer.get_token(user)
    return f"Bearer {token.access_token}"


def make_campus(name, city, latitude, longitude, **extra):
    """Create a Campus with a properly-constructed PostGIS Point."""
    return Campus.objects.create(
        name=name,
        city=city,
        location=Point(longitude, latitude, srid=4326),
        **extra,
    )


# Two campuses ~14 km apart (both in Bengaluru) and one ~67 km further
# away (Tumakuru) — comfortably clear of both the 20 km default radius
# (excluded by default) and a 100 km widened radius (included once
# widened), so tests never hinge on a borderline distance calculation.
BENGALURU_CAMPUS_A = {"name": "Alpha Institute of Technology", "city": "Bengaluru", "latitude": 12.9716, "longitude": 77.5946}
BENGALURU_CAMPUS_B = {"name": "Beta College of Engineering", "city": "Bengaluru", "latitude": 12.9716, "longitude": 77.7246}
TUMAKURU_CAMPUS_FAR = {"name": "Gamma University", "city": "Tumakuru", "latitude": 13.3379, "longitude": 77.1022}
