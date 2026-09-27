import django_rq
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from summaries.models import ReviewSummary
from summaries.serializers import ReviewSummarySerializer
from summaries.tasks import summarise_reviews


def summaries_visible_to(user):
    """Admin sees every summary, a provider only their own."""
    qs = ReviewSummary.objects.all()
    if user.is_admin_role:
        return qs
    return qs.filter(provider=user)


class SummariseView(APIView):
    """
    POST /api/providers/{id}/summarise/

    Creates a 'queued' ReviewSummary row, puts a job on the Redis queue and
    returns 202 immediately; the worker does the actual work. Admin may
    summarise any provider, a provider only themselves (RBACMiddleware
    already rejected every other role).
    """

    def post(self, request, provider_id):
        user = request.user
        if user.is_provider and user.id != provider_id:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        provider = get_object_or_404(User, pk=provider_id, role=User.Role.PROVIDER)

        in_flight = ReviewSummary.objects.filter(
            provider=provider,
            status__in=[ReviewSummary.Status.QUEUED, ReviewSummary.Status.RUNNING],
        ).first()
        if in_flight:
            # Don't queue a duplicate; point the client at the existing job.
            return Response(
                ReviewSummarySerializer(in_flight).data, status=status.HTTP_202_ACCEPTED
            )

        try:
            with transaction.atomic():
                summary = ReviewSummary.objects.create(provider=provider, requested_by=user)
                # Enqueue only after the row is committed, otherwise a fast
                # worker could look for a row that doesn't exist yet.
                transaction.on_commit(lambda: enqueue_summary(summary))
        except IntegrityError:
            # Another request created one between our check and insert.
            summary = ReviewSummary.objects.get(
                provider=provider,
                status__in=[ReviewSummary.Status.QUEUED, ReviewSummary.Status.RUNNING],
            )

        return Response(ReviewSummarySerializer(summary).data, status=status.HTTP_202_ACCEPTED)


def enqueue_summary(summary):
    job = django_rq.enqueue(summarise_reviews, summary.id)
    summary.job_id = job.id
    summary.save(update_fields=["job_id"])


class ReviewSummaryViewSet(viewsets.ReadOnlyModelViewSet):
    """GET /api/summaries/ and /api/summaries/{id}/, polled for the result."""

    serializer_class = ReviewSummarySerializer

    def get_queryset(self):
        return summaries_visible_to(self.request.user)
