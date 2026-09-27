from rest_framework.routers import DefaultRouter

from bookings.views import BookingViewSet, SlotViewSet

router = DefaultRouter()
router.register("slots", SlotViewSet, basename="slot")
router.register("bookings", BookingViewSet, basename="booking")

urlpatterns = router.urls
