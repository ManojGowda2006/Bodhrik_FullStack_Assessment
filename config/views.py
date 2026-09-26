from django.db import connection
from django.http import JsonResponse


def health(request):
    """Liveness + DB check. Used by docker-compose and CI smoke tests."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        db = "ok"
    except Exception:
        db = "unavailable"

    status = 200 if db == "ok" else 503
    return JsonResponse({"status": "ok" if status == 200 else "degraded", "db": db}, status=status)
