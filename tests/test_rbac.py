"""
The brief's access rules: a provider cannot read another provider's
bookings, and a customer can only read their own. Plus role checks.
"""

import pytest

from bookings.models import Booking

pytestmark = pytest.mark.django_db


@pytest.fixture
def bookings(make_booking, provider_a, provider_b, customer_1, customer_2):
    """booking_a: provider_a/customer_1, booking_b: provider_b/customer_2."""
    return {
        "a": make_booking(provider_a, customer_1),
        "b": make_booking(provider_b, customer_2),
    }


def ids(response):
    return sorted(row["id"] for row in response.json()["results"])


# --- rows: who sees which bookings -------------------------------------------


def test_admin_sees_all_bookings(client_for, admin, bookings):
    assert ids(client_for(admin).get("/api/bookings/")) == sorted(
        [bookings["a"].id, bookings["b"].id]
    )


def test_provider_lists_only_own_bookings(client_for, provider_a, bookings):
    assert ids(client_for(provider_a).get("/api/bookings/")) == [bookings["a"].id]


def test_customer_lists_only_own_bookings(client_for, customer_2, bookings):
    assert ids(client_for(customer_2).get("/api/bookings/")) == [bookings["b"].id]


def test_provider_cannot_read_other_providers_booking(client_for, provider_b, bookings):
    response = client_for(provider_b).get(f"/api/bookings/{bookings['a'].id}/")
    assert response.status_code == 404  # not 403: don't reveal it exists


def test_customer_cannot_read_other_customers_booking(client_for, customer_2, bookings):
    assert client_for(customer_2).get(f"/api/bookings/{bookings['a'].id}/").status_code == 404


def test_provider_cannot_update_other_providers_booking(client_for, provider_b, bookings):
    response = client_for(provider_b).patch(
        f"/api/bookings/{bookings['a'].id}/", {"status": "confirmed"}, format="json"
    )
    assert response.status_code == 404
    bookings["a"].refresh_from_db()
    assert bookings["a"].status == Booking.Status.PENDING


# --- roles: who may call what (RBACMiddleware) --------------------------------


def test_anonymous_gets_401(client_for):
    assert client_for().get("/api/bookings/").status_code == 401


@pytest.mark.parametrize(
    ("role_fixture", "method", "url", "expected"),
    [
        ("provider_a", "post", "/api/bookings/", 403),  # only customers book
        ("admin", "post", "/api/bookings/", 403),
        ("customer_1", "post", "/api/slots/", 403),  # only providers create slots
        ("customer_1", "delete", "/api/bookings/{a}/", 403),  # only admin deletes
        ("provider_a", "delete", "/api/bookings/{a}/", 403),
        ("provider_a", "post", "/api/bookings/{a}/review/", 403),  # only customers review
        ("customer_1", "post", "/api/providers/{pa}/summarise/", 403),
        ("customer_1", "get", "/api/summaries/", 403),
    ],
)
def test_role_policy(
    request, client_for, bookings, provider_a, role_fixture, method, url, expected
):
    user = request.getfixturevalue(role_fixture)
    url = url.format(a=bookings["a"].id, pa=provider_a.id)
    response = getattr(client_for(user), method)(url, {}, format="json")
    assert response.status_code == expected


def test_admin_can_delete_booking(client_for, admin, bookings):
    assert client_for(admin).delete(f"/api/bookings/{bookings['a'].id}/").status_code == 204
    assert not Booking.objects.filter(pk=bookings["a"].id).exists()
