from django.utils import timezone
from rest_framework import serializers

from bookings.models import Slot


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
