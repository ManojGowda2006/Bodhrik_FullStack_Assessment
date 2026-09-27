from django.db.models import Exists, OuterRef
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from accounts.permissions import IsAdminRole, IsCustomer, IsProvider
from bookings.models import Booking, Slot
from bookings.serializers import (
    BookingCreateSerializer,
    BookingSerializer,
    BookingStatusSerializer,
    ReviewSerializer,
    SlotSerializer,
)


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


class BookingViewSet(viewsets.ModelViewSet):
    """
    CRUD on bookings. Two layers of access control:

    1. Role (permission classes, 403): who may call each action.
       create -> customer, destroy -> admin, review -> customer,
       list / retrieve / partial_update -> any logged-in user.
    2. Rows (get_queryset, 404): every action only ever sees
       Booking.objects.visible_to(user), so a provider can't read
       another provider's bookings and a customer only sees their own.

    Status changes (PATCH) are limited per role by Booking.TRANSITIONS.
    Customers cancel with PATCH; DELETE is an admin-only hard delete.
    """

    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_permissions(self):
        if self.action in ("create", "review"):
            return [IsCustomer()]
        if self.action == "destroy":
            return [IsAdminRole()]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        qs = Booking.objects.visible_to(self.request.user).select_related("slot", "review")
        status_filter = self.request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)
        return qs

    def get_serializer_class(self):
        if self.action == "create":
            return BookingCreateSerializer
        if self.action == "partial_update":
            return BookingStatusSerializer
        return BookingSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        booking = serializer.save()
        return Response(BookingSerializer(booking).data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs):
        booking = self.get_object()
        serializer = self.get_serializer(booking, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(BookingSerializer(booking).data)

    @action(detail=True, methods=["post"])
    def review(self, request, pk=None):
        # IsCustomer + visible_to() mean this is always the caller's own booking;
        # anyone else's is a 404.
        booking = self.get_object()
        serializer = ReviewSerializer(data=request.data, context={"booking": booking})
        serializer.is_valid(raise_exception=True)
        serializer.save(booking=booking)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
