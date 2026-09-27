from django.db.models import Exists, OuterRef
from rest_framework import permissions, status, viewsets
from rest_framework.response import Response

from accounts.permissions import IsProvider
from bookings.models import Booking, Slot
from bookings.serializers import SlotSerializer


class SlotViewSet(viewsets.ModelViewSet):
    """
    Any logged-in user can browse slots (customers need to, to book).
    Only providers create slots, and only for themselves.
    A provider can delete their own slot while it has never been booked.

    Filters: ?provider=<id>  ?available=true
    """

    serializer_class = SlotSerializer
    http_method_names = ["get", "post", "delete", "head", "options"]

    def get_permissions(self):
        if self.action in ("create", "destroy"):
            return [IsProvider()]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        active_booking = Booking.objects.filter(slot=OuterRef("pk")).exclude(
            status=Booking.Status.CANCELLED
        )
        qs = Slot.objects.annotate(is_available=~Exists(active_booking))

        if self.action == "destroy":
            # Another provider's slot is simply not found (404).
            return qs.filter(provider=self.request.user)

        provider = self.request.query_params.get("provider")
        if provider:
            qs = qs.filter(provider_id=provider)
        if self.request.query_params.get("available") == "true":
            qs = qs.filter(is_available=True)
        return qs

    def perform_create(self, serializer):
        slot = serializer.save(provider=self.request.user)
        slot.is_available = True  # new slot, no bookings yet (not annotated)

    def destroy(self, request, *args, **kwargs):
        slot = self.get_object()
        if slot.bookings.exists():
            return Response(
                {"detail": "Slot has bookings and can't be deleted."},
                status=status.HTTP_409_CONFLICT,
            )
        slot.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
