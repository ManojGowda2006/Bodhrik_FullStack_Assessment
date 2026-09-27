from django.db.models import Exists, OuterRef
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from bookings.cache import get_slot_list, set_slot_list
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
    Only providers create slots (enforced by RBACMiddleware), always for
    themselves. A provider can delete their own never-booked slot.

    Filters: ?provider=<id>  ?available=true
    The list is cached in Redis (see bookings/cache.py).
    """

    serializer_class = SlotSerializer
    http_method_names = ["get", "post", "delete", "head", "options"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):  # API docs generation, no real user
            return Slot.objects.none()
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

    def list(self, request, *args, **kwargs):
        key, cached = get_slot_list(request.query_params)
        if cached is not None:
            return Response(cached, headers={"X-Cache": "HIT"})
        response = super().list(request, *args, **kwargs)
        set_slot_list(key, response.data)
        response["X-Cache"] = "MISS"
        return response

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

    1. Role (RBACMiddleware, 403): who may call each route.
       create -> customer, destroy -> admin, review -> customer,
       list / retrieve / partial_update -> any logged-in user.
    2. Rows (get_queryset here, 404): every action only ever sees
       Booking.objects.visible_to(user), so a provider can't read
       another provider's bookings and a customer only sees their own.

    Status changes (PATCH) are limited per role by Booking.TRANSITIONS.
    Customers cancel with PATCH; DELETE is an admin-only hard delete.
    """

    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):  # API docs generation, no real user
            return Booking.objects.none()
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

    @extend_schema(request=BookingCreateSerializer, responses={201: BookingSerializer})
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        booking = serializer.save()
        return Response(BookingSerializer(booking).data, status=status.HTTP_201_CREATED)

    @extend_schema(request=BookingStatusSerializer, responses=BookingSerializer)
    def partial_update(self, request, *args, **kwargs):
        booking = self.get_object()
        serializer = self.get_serializer(booking, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(BookingSerializer(booking).data)

    @extend_schema(request=ReviewSerializer, responses={201: ReviewSerializer})
    @action(detail=True, methods=["post"])
    def review(self, request, pk=None):
        # Middleware allows only customers here, and visible_to() limits a
        # customer to their own bookings, so this is always the caller's own;
        # anyone else's is a 404.
        booking = self.get_object()
        serializer = ReviewSerializer(data=request.data, context={"booking": booking})
        serializer.is_valid(raise_exception=True)
        serializer.save(booking=booking)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
