"""HTTP request logging middleware for Amanat-yab."""

import logging
import time

logger = logging.getLogger("amanatyab.core")


class RequestLogMiddleware:
    """Middleware that logs each HTTP request (method, path, user id, status, duration in ms)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start_time = time.monotonic()
        try:
            response = self.get_response(request)
        except Exception:
            duration_ms = (time.monotonic() - start_time) * 1000
            user = getattr(request, "user", None)
            user_id = (
                user.pk
                if (user and getattr(user, "is_authenticated", False) and user.pk is not None)
                else "anonymous"
            )
            logger.exception(
                "%s %s user=%s status=500 duration=%.2fms",
                request.method,
                request.get_full_path(),
                user_id,
                duration_ms,
            )
            raise

        duration_ms = (time.monotonic() - start_time) * 1000
        user = getattr(request, "user", None)
        user_id = (
            user.pk
            if (user and getattr(user, "is_authenticated", False) and user.pk is not None)
            else "anonymous"
        )
        status_code = getattr(response, "status_code", 200)

        logger.info(
            "%s %s user=%s status=%s duration=%.2fms",
            request.method,
            request.get_full_path(),
            user_id,
            status_code,
            duration_ms,
        )
        return response
