from drf_spectacular.extensions import OpenApiAuthenticationExtension


class MiddlewareUserAuthenticationScheme(OpenApiAuthenticationExtension):
    """
    Tells the OpenAPI schema that our API uses Bearer JWTs.

    drf-spectacular recognises simplejwt's own auth class, but not our
    MiddlewareUserAuthentication, so without this Swagger UI would show
    no "Authorize" button.
    """

    target_class = "accounts.authentication.MiddlewareUserAuthentication"
    name = "jwtAuth"

    def get_security_definition(self, auto_schema):
        return {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"}
