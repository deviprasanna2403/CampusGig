"""
Custom DRF exception handler.

Every error response (validation errors, auth failures, permission
denials, throttling, 404s, etc.) is normalized to:

    {
        "success": false,
        "data": null,
        "error": {
            "code": <http status int>,
            "message": <short human-readable summary>,
            "details": <field-level errors, or null>
        }
    }

This only touches error responses. Successful responses are returned by
each view/serializer as-is (see Phase 1, section 2.3, for the original
full-envelope idea — applying it to *success* responses too would mean
wrapping third-party views such as SimpleJWT's TokenObtainPairView/
TokenRefreshView, which would fight their own response schemas. Doing
that consistently, project-wide, is deferred to a later phase via a
custom renderer rather than done partially here.
"""

from rest_framework.views import exception_handler as drf_exception_handler


def custom_exception_handler(exc, context):
    response = drf_exception_handler(exc, context)
    if response is None:
        # Not a DRF-recognized exception (e.g. an unhandled Python
        # exception) — let Django's normal 500 handling take over.
        return response

    detail = response.data

    if isinstance(detail, dict) and set(detail.keys()) == {"detail"}:
        # Single top-level error, e.g. authentication/permission failures,
        # simplejwt's "No active account found with the given credentials".
        message = str(detail["detail"])
        details = None
    elif isinstance(detail, dict):
        # Field-level validation errors from a serializer.
        message = "Validation failed."
        details = detail
    elif isinstance(detail, list):
        message = "Validation failed."
        details = {"non_field_errors": detail}
    else:
        message = str(detail)
        details = None

    response.data = {
        "success": False,
        "data": None,
        "error": {
            "code": response.status_code,
            "message": message,
            "details": details,
        },
    }
    return response
