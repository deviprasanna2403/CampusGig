from django.conf import settings
from django.http import JsonResponse


def health_check(request):
    """
    Unauthenticated liveness endpoint. Confirms settings load correctly
    and the app boots — does not touch the database, so it stays useful
    even if migrations haven't been run yet.
    """
    return JsonResponse(
        {
            "status": "ok",
            "project": "CampusGig",
            "phase": 2,
            "debug": settings.DEBUG,
        }
    )
