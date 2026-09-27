from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework import serializers

from bookings.models import Booking, Review, Slot


class SlotSerializer(serializers.ModelSerializer):
    # Computed in the queryset (SlotViewSet.get_queryset), not a column.
    is_available = serializers.BooleanField(read_only=True)

    class Meta:
        model = Slot
        fields = ("id", "provider", "start_time", "end_time", "is_available", "created_at")
        # provider is always the logged-in provider, never taken from input.
        read_only_fields = ("provider", "created_at")

    def validate(self, attrs):
        if attrs["end_time"] <= attrs["start_time"]:
            raise serializers.ValidationError({"end_time": "Must be after start_time."})
        if attrs["start_time"] <= timezone.now():
            raise serializers.ValidationError({"start_time": "Must be in the future."})
        provider = self.context["request"].user
        if Slot.objects.filter(provider=provider, start_time=attrs["start_time"]).exists():
            raise serializers.ValidationError(
                {"start_time": "You already have a slot at this time."}
            )
        return attrs


class ReviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = Review
        fields = ("id", "booking", "rating", "comment", "created_at")
        read_only_fields = ("booking", "created_at")

    def validate(self, attrs):
        booking = self.context["booking"]
        if booking.status != Booking.Status.COMPLETED:
            raise serializers.ValidationError("Only completed bookings can be reviewed.")
        if hasattr(booking, "review"):
            raise serializers.ValidationError("This booking has already been reviewed.")
        return attrs

    def create(self, validated_data):
        try:
            with transaction.atomic():
                return super().create(validated_data)
        except IntegrityError:
            # Two requests raced past validate(); the OneToOne index caught it.
            raise serializers.ValidationError("This booking has already been reviewed.") from None


class BookingSerializer(serializers.ModelSerializer):
    """Read shape for bookings (list / retrieve / responses)."""

    slot = SlotSerializer(read_only=True)
    review = ReviewSerializer(read_only=True)

    class Meta:
        model = Booking
        fields = (
            "id",
            "slot",
            "customer",
            "provider",
            "status",
            "review",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class BookingCreateSerializer(serializers.ModelSerializer):
    """Customer books a slot. Only the slot comes from input."""

    class Meta:
        model = Booking
        fields = ("slot",)

    def validate_slot(self, slot):
        if slot.start_time <= timezone.now():
            raise serializers.ValidationError("This slot has already started.")
        if slot.bookings.exclude(status=Booking.Status.CANCELLED).exists():
            raise serializers.ValidationError("This slot is already booked.")
        return slot

    def create(self, validated_data):
        slot = validated_data["slot"]
        try:
            with transaction.atomic():
                return Booking.objects.create(
                    slot=slot,
                    customer=self.context["request"].user,
                    provider=slot.provider,  # copied from the slot, never from input
                )
        except IntegrityError:
            # Two customers raced past validate_slot(); the partial unique index won.
            raise serializers.ValidationError({"slot": "This slot is already booked."}) from None


class BookingStatusSerializer(serializers.ModelSerializer):
    """PATCH: the only editable field is status, following Booking.TRANSITIONS."""

    class Meta:
        model = Booking
        fields = ("status",)

    def validate_status(self, value):
        role = self.context["request"].user.role
        if value not in self.instance.allowed_next_statuses(role):
            raise serializers.ValidationError(
                f"A {role} can't change a booking from {self.instance.status} to {value}."
            )
        return value
