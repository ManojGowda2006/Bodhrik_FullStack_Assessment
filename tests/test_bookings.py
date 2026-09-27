import pytest

from bookings.models import Booking

pytestmark = pytest.mark.django_db


def book(client, slot):
    return client.post("/api/bookings/", {"slot": slot.id}, format="json")


def set_status(client, booking, status):
    return client.patch(f"/api/bookings/{booking.id}/", {"status": status}, format="json")


def test_customer_books_slot_provider_copied_from_slot(
    client_for, customer_1, provider_a, make_slot
):
    response = book(client_for(customer_1), make_slot(provider_a))
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "pending"
    assert body["customer"] == customer_1.id and body["provider"] == provider_a.id


def test_double_booking_rejected(client_for, customer_1, customer_2, provider_a, make_slot):
    slot = make_slot(provider_a)
    assert book(client_for(customer_1), slot).status_code == 201
    response = book(client_for(customer_2), slot)
    assert response.status_code == 400
    assert Booking.objects.filter(slot=slot).count() == 1


def test_cancelled_booking_frees_slot(client_for, customer_1, customer_2, provider_a, make_slot):
    slot = make_slot(provider_a)
    booking_id = book(client_for(customer_1), slot).json()["id"]
    assert (
        set_status(client_for(customer_1), Booking(pk=booking_id), "cancelled").status_code == 200
    )
    assert book(client_for(customer_2), slot).status_code == 201


def test_provider_confirms_then_completes(client_for, provider_a, customer_1, make_booking):
    booking = make_booking(provider_a, customer_1)
    client = client_for(provider_a)
    assert set_status(client, booking, "completed").status_code == 400  # can't skip confirmed
    assert set_status(client, booking, "confirmed").json()["status"] == "confirmed"
    assert set_status(client, booking, "completed").json()["status"] == "completed"


def test_customer_cannot_confirm(client_for, provider_a, customer_1, make_booking):
    booking = make_booking(provider_a, customer_1)
    assert set_status(client_for(customer_1), booking, "confirmed").status_code == 400


def test_completed_booking_cannot_be_cancelled(client_for, provider_a, customer_1, make_booking):
    booking = make_booking(provider_a, customer_1, status=Booking.Status.COMPLETED)
    assert set_status(client_for(customer_1), booking, "cancelled").status_code == 400


# --- reviews ------------------------------------------------------------------


def review(client, booking, **data):
    return client.post(f"/api/bookings/{booking.id}/review/", data, format="json")


def test_review_completed_booking(client_for, provider_a, customer_1, make_booking):
    booking = make_booking(provider_a, customer_1, status=Booking.Status.COMPLETED)
    response = review(client_for(customer_1), booking, rating=5, comment="Great")
    assert response.status_code == 201
    detail = client_for(customer_1).get(f"/api/bookings/{booking.id}/").json()
    assert detail["review"]["rating"] == 5


def test_cannot_review_unfinished_booking(client_for, provider_a, customer_1, make_booking):
    booking = make_booking(provider_a, customer_1, status=Booking.Status.CONFIRMED)
    assert review(client_for(customer_1), booking, rating=5).status_code == 400


def test_only_one_review_per_booking(client_for, provider_a, customer_1, make_booking):
    booking = make_booking(provider_a, customer_1, status=Booking.Status.COMPLETED)
    assert review(client_for(customer_1), booking, rating=5).status_code == 201
    assert review(client_for(customer_1), booking, rating=1).status_code == 400


@pytest.mark.parametrize("rating", [0, 6])
def test_rating_must_be_1_to_5(client_for, provider_a, customer_1, make_booking, rating):
    booking = make_booking(provider_a, customer_1, status=Booking.Status.COMPLETED)
    assert review(client_for(customer_1), booking, rating=rating).status_code == 400


def test_cannot_review_someone_elses_booking(
    client_for, provider_a, customer_1, customer_2, make_booking
):
    booking = make_booking(provider_a, customer_1, status=Booking.Status.COMPLETED)
    assert review(client_for(customer_2), booking, rating=1).status_code == 404
