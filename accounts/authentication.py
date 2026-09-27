from rest_framework.authentication import BaseAuthentication


class MiddlewareUserAuthentication(BaseAuthentication):
    """
    Hands DRF the user that RBACMiddleware already authenticated.

    DRF normally authenticates inside the view; here the middleware has
    done it once already, so this just passes the result through instead
    of decoding the JWT and loading the user a second time.
    """

    def authenticate(self, request):
        user = getattr(request._request, "user", None)
        if user is not None and user.is_authenticated:
            return (user, None)
        return None
