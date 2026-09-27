import pytest

pytestmark = pytest.mark.django_db


def create_slot(client, start="2099-01-01T10:00:00Z", end="2099-01-01T11:00:00Z"):
    return client.post("/api/slots/", {"start_time": start, "end_time": end}, format="json")


def test_provider_creates_slot_for_themselves(client_for, provider_a):
    response = create_slot(client_for(provider_a))
    assert response.status_code == 201
    assert response.json()["provider"] == provider_a.id
    assert response.json()["is_available"] is True


def test_slot_validation(client_for, provider_a):
    client = client_for(provider_a)
    assert (
        create_slot(client, start="2099-01-01T11:00:00Z", end="2099-01-01T10:00:00Z").status_code
        == 400
    )
    assert (
        create_slot(client, start="2020-01-01T10:00:00Z", end="2020-01-01T11:00:00Z").status_code
        == 400
    )


def test_provider_cannot_delete_other_providers_slot(client_for, provider_a, provider_b, make_slot):
    slot = make_slot(provider_a)
    assert client_for(provider_b).delete(f"/api/slots/{slot.id}/").status_code == 404
    assert client_for(provider_a).delete(f"/api/slots/{slot.id}/").status_code == 204


def test_slot_list_cached_then_invalidated_by_booking(
    client_for, customer_1, provider_a, make_slot, django_capture_on_commit_callbacks
):
    slot = make_slot(provider_a)
    client = client_for(customer_1)

    first = client.get("/api/slots/")
    second = client.get("/api/slots/")
    assert first["X-Cache"] == "MISS"
    assert second["X-Cache"] == "HIT"
    assert second.json()["results"][0]["is_available"] is True

    # Invalidation runs on commit; tests run inside a transaction, so run
    # the on_commit callbacks explicitly.
    with django_capture_on_commit_callbacks(execute=True):
        client.post("/api/bookings/", {"slot": slot.id}, format="json")

    after = client.get("/api/slots/")
    assert after["X-Cache"] == "MISS"
    assert after.json()["results"][0]["is_available"] is False


def test_available_filter(client_for, customer_1, provider_a, make_slot, make_booking):
    free = make_slot(provider_a)
    make_booking(provider_a, customer_1)  # books a second slot
    rows = client_for(customer_1).get("/api/slots/?available=true").json()["results"]
    assert [row["id"] for row in rows] == [free.id]
