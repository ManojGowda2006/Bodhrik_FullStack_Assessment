from rest_framework.routers import DefaultRouter

from bookings.views import SlotViewSet

router = DefaultRouter()
router.register("slots", SlotViewSet, basename="slot")

urlpatterns = router.urls
