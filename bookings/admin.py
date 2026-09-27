from django.contrib import admin

from bookings.models import Booking, Review, Slot


@admin.register(Slot)
class SlotAdmin(admin.ModelAdmin):
    list_display = ("id", "provider", "start_time", "end_time")
    list_filter = ("provider",)


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ("id", "slot", "customer", "provider", "status", "created_at")
    list_filter = ("status",)


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("id", "booking", "rating", "created_at")
