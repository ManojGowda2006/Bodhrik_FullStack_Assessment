from rest_framework import serializers

from summaries.models import ReviewSummary


class ReviewSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = ReviewSummary
        fields = (
            "id",
            "provider",
            "status",
            "review_count",
            "average_rating",
            "summary",
            "error",
            "created_at",
            "completed_at",
        )
        read_only_fields = fields
