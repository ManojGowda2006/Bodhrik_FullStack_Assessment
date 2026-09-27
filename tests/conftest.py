from datetime import timedelta

import pytest
from django.core.cache import cache
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import User
from bookings.models import Booking, Review, Slot


@pytest.fixture(autouse=True)
def clean_redis():
    """Tests use Redis DB 15 (settings_test); start every test empty."""
    cache.clear()  # FLUSHDB: also empties the RQ queue in the same DB
    yield


def make_user(username, role):
    return User.objects.create_user(
        username=username, email=f"{username}@example.com", password="S3cure-pass!", role=role
    )


@pytest.fixture
def admin(db):
    return make_user("admin", User.Role.ADMIN)


@pytest.fixture
def provider_a(db):
    return make_user("provider_a", User.Role.PROVIDER)


@pytest.fixture
def provider_b(db):
    return make_user("provider_b", User.Role.PROVIDER)


@pytest.fixture
def customer_1(db):
    return make_user("customer_1", User.Role.CUSTOMER)


@pytest.fixture
def customer_2(db):
    return make_user("customer_2", User.Role.CUSTOMER)


@pytest.fixture
def client_for():
    """client_for(user) -> APIClient sending that user's JWT (None = anonymous).

    Real tokens, so every request goes through RBACMiddleware like production.
    """

    def _client(user=None):
        client = APIClient()
        if user is not None:
            token = RefreshToken.for_user(user).access_token
            client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        return client

    return _client


@pytest.fixture
def make_slot():
    counter = {"n": 0}

    def _slot(provider, days_ahead=1):
        counter["n"] += 1
        start = timezone.now() + timedelta(days=days_ahead, hours=counter["n"])
        return Slot.objects.create(
            provider=provider, start_time=start, end_time=start + timedelta(hours=1)
        )

    return _slot


@pytest.fixture
def make_booking(make_slot):
    def _booking(provider, customer, status=Booking.Status.PENDING, rating=None, comment=""):
        slot = make_slot(provider)
        booking = Booking.objects.create(
            slot=slot, customer=customer, provider=provider, status=status
        )
        if rating is not None:
            Review.objects.create(booking=booking, rating=rating, comment=comment)
        return booking

    return _booking
