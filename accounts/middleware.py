"""
Role-based access control middleware for the /api/ routes.

For every API request it:
1. authenticates the JWT (401 if missing or invalid), except public routes,
2. checks the caller's role against ROLE_POLICY for the matched route and
   HTTP method (403 if the role isn't allowed).

Which *rows* a user may see can't be decided here: middleware runs before
the view loads any objects. That stays in the querysets, e.g.
Booking.objects.visible_to(user), which returns 404 for other users' rows.
"""

from django.http import JsonResponse
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication

# URL names that need no token.
PUBLIC_ROUTES = {"health", "register", "token", "token-refresh"}

# (URL name, HTTP method) -> roles allowed to call it.
# Any /api/ route not listed is open to every authenticated user, and its
# view's queryset still limits which rows they get.
ROLE_POLICY = {
    ("slot-list", "POST"): {"provider"},
    ("slot-detail", "DELETE"): {"provider"},
    ("booking-list", "POST"): {"customer"},
    ("booking-detail", "DELETE"): {"admin"},
    ("booking-review", "POST"): {"customer"},
    ("provider-summarise", "POST"): {"admin", "provider"},
    ("summary-list", "GET"): {"admin", "provider"},
    ("summary-detail", "GET"): {"admin", "provider"},
}


class RBACMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.jwt = JWTAuthentication()

    def __call__(self, request):
        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        # process_view runs after URL resolution, so we know the route name.
        if not request.path.startswith("/api/"):
            return None  # e.g. the Django admin, which uses its own session login

        route = request.resolver_match.url_name
        if route in PUBLIC_ROUTES:
            return None

        try:
            result = self.jwt.authenticate(request)
        except AuthenticationFailed:
            return JsonResponse({"detail": "Invalid or expired token."}, status=401)
        if result is None:
            return JsonResponse(
                {"detail": "Authentication credentials were not provided."}, status=401
            )

        request.user = result[0]  # loaded from the DB, so role changes apply at once

        allowed_roles = ROLE_POLICY.get((route, request.method))
        if allowed_roles is not None and request.user.role not in allowed_roles:
            return JsonResponse({"detail": "Your role can't perform this action."}, status=403)
        return None
