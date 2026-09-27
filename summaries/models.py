from django.conf import settings
from django.db import models


class ReviewSummary(models.Model):
    """
    One summarisation run for a provider's reviews.

    The row is created as 'queued' by the API, then the worker moves it to
    'running' and finally 'done' or 'failed'. Clients poll this row.
    Postgres is the source of truth; Redis only carries the job.
    """

    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        RUNNING = "running", "Running"
        DONE = "done", "Done"
        FAILED = "failed", "Failed"

    provider = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="review_summaries"
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.QUEUED)
    job_id = models.CharField(max_length=64, blank=True)
    review_count = models.PositiveIntegerField(null=True, blank=True)
    average_rating = models.DecimalField(max_digits=3, decimal_places=2, null=True, blank=True)
    summary = models.TextField(blank=True)
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "review summaries"
        constraints = [
            # At most one summary in flight per provider, so repeated clicks
            # don't pile duplicate jobs onto the queue.
            models.UniqueConstraint(
                fields=["provider"],
                condition=models.Q(status__in=["queued", "running"]),
                name="summary_one_in_flight_per_provider",
            ),
        ]

    def __str__(self):
        return f"Summary {self.pk} provider={self.provider_id} {self.status}"
