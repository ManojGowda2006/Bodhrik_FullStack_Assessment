import jwt
import pytest

from accounts.models import User

pytestmark = pytest.mark.django_db


def register(client, **overrides):
    data = {"username": "new", "email": "new@example.com", "password": "S3cure-pass!"}
    data.update(overrides)
    return client.post("/api/auth/register/", data, format="json")


def test_health_is_public(client_for):
    response = client_for().get("/api/health/")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "db": "ok"}


def test_register_defaults_to_customer_and_hashes_password(client_for):
    response = register(client_for())
    assert response.status_code == 201
    assert "password" not in response.json()
    user = User.objects.get(username="new")
    assert user.role == User.Role.CUSTOMER
    assert user.password != "S3cure-pass!" and user.check_password("S3cure-pass!")


def test_register_as_provider(client_for):
    assert register(client_for(), role="provider").json()["role"] == "provider"


def test_cannot_self_register_as_admin(client_for):
    response = register(client_for(), role="admin")
    assert response.status_code == 400
    assert not User.objects.filter(username="new").exists()


def test_weak_password_rejected(client_for):
    assert register(client_for(), password="123").status_code == 400


def test_login_returns_tokens_with_role_claim(client_for, provider_a):
    response = client_for().post(
        "/api/auth/token/", {"username": "provider_a", "password": "S3cure-pass!"}, format="json"
    )
    assert response.status_code == 200
    claims = jwt.decode(response.json()["access"], options={"verify_signature": False})
    assert claims["role"] == "provider"


def test_login_wrong_password(client_for, provider_a):
    response = client_for().post(
        "/api/auth/token/", {"username": "provider_a", "password": "wrong"}, format="json"
    )
    assert response.status_code == 401


def test_me_requires_token(client_for, customer_1):
    assert client_for().get("/api/auth/me/").status_code == 401
    assert client_for(customer_1).get("/api/auth/me/").json()["username"] == "customer_1"


def test_invalid_token_rejected_by_middleware(client_for):
    client = client_for()
    client.credentials(HTTP_AUTHORIZATION="Bearer not.a.token")
    response = client.get("/api/bookings/")
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid or expired token."


def test_createsuperuser_gets_admin_role():
    user = User.objects.create_superuser("root", "root@example.com", "S3cure-pass!")
    assert user.role == User.Role.ADMIN and user.is_superuser
