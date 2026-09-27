from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import F, Q


class Slot(models.Model):
    """
    A time window a provider offers.

    There is no is_booked column: availability is derived from whether an
    active booking exists, so it can never drift out of sync.
    """

    provider = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="slots"
    )
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["start_time"]
        indexes = [models.Index(fields=["provider", "start_time"])]
        constraints = [
            models.CheckConstraint(
                condition=Q(end_time__gt=F("start_time")), name="slot_end_after_start"
            ),
            models.UniqueConstraint(
                fields=["provider", "start_time"], name="slot_unique_provider_start"
            ),
        ]

    def __str__(self):
        return f"Slot {self.pk} ({self.provider_id}) {self.start_time:%Y-%m-%d %H:%M}"


class BookingQuerySet(models.QuerySet):
    def visible_to(self, user):
        """
        Row-level access control for bookings, in one place.

        admin sees everything, a provider only bookings of their own slots,
        a customer only their own bookings. Anything outside this queryset
        returns 404 from the API, so we never reveal that it exists.
        """
        if user.is_admin_role:
            return self
        if user.is_provider:
            return self.filter(provider=user)
        if user.is_customer:
            return self.filter(customer=user)
        return self.none()


class Booking(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        CONFIRMED = "confirmed", "Confirmed"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    # Which status changes each role may make: {current: {allowed next}}.
    TRANSITIONS = {
        "customer": {
            Status.PENDING: {Status.CANCELLED},
            Status.CONFIRMED: {Status.CANCELLED},
        },
        "provider": {
            Status.PENDING: {Status.CONFIRMED, Status.CANCELLED},
            Status.CONFIRMED: {Status.COMPLETED, Status.CANCELLED},
        },
        "admin": {
            Status.PENDING: {Status.CONFIRMED, Status.CANCELLED},
            Status.CONFIRMED: {Status.COMPLETED, Status.CANCELLED},
        },
    }

    # PROTECT: bookings are history; a slot or user with bookings can't be deleted.
    slot = models.ForeignKey(Slot, on_delete=models.PROTECT, related_name="bookings")
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="customer_bookings"
    )
    # Denormalised copy of slot.provider, so provider scoping is one indexed
    # column instead of a join. Always set from the slot, never from input.
    provider = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="provider_bookings"
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = BookingQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            # At most one non-cancelled booking per slot: the DB prevents
            # double-booking even if two requests race. A cancelled booking
            # frees the slot to be booked again.
            models.UniqueConstraint(
                fields=["slot"],
                condition=~Q(status="cancelled"),
                name="booking_one_active_per_slot",
            ),
            models.CheckConstraint(
                condition=Q(status__in=["pending", "confirmed", "completed", "cancelled"]),
                name="booking_status_valid",
            ),
        ]

    def __str__(self):
        return f"Booking {self.pk} slot={self.slot_id} {self.status}"

    def allowed_next_statuses(self, role):
        return self.TRANSITIONS.get(role, {}).get(self.status, set())


class Review(models.Model):
    # OneToOne: at most one review per booking, enforced by a unique index.
    # Customer and provider are reachable through the booking, so not copied.
    booking = models.OneToOneField(Booking, on_delete=models.CASCADE, related_name="review")
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=Q(rating__gte=1, rating__lte=5), name="review_rating_1_to_5"
            ),
        ]

    def __str__(self):
        return f"Review {self.pk} booking={self.booking_id} {self.rating}/5"
