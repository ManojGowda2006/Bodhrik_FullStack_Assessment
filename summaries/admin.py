from django.contrib import admin

from summaries.models import ReviewSummary


@admin.register(ReviewSummary)
class ReviewSummaryAdmin(admin.ModelAdmin):
    list_display = ("id", "provider", "status", "review_count", "average_rating", "created_at")
    list_filter = ("status",)
