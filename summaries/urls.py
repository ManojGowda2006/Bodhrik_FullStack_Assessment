from django.urls import path
from rest_framework.routers import DefaultRouter

from summaries.views import ReviewSummaryViewSet, SummariseView

router = DefaultRouter()
router.register("summaries", ReviewSummaryViewSet, basename="summary")

urlpatterns = [
    path(
        "providers/<int:provider_id>/summarise/",
        SummariseView.as_view(),
        name="provider-summarise",
    ),
    *router.urls,
]
