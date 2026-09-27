"""
Jobs run by the RQ worker (python manage.py rqworker), not by the API.

The API enqueues summarise_reviews(summary_id). RQ stores the function's
import path and the id in Redis; the worker imports this module and calls it.
We pass only an id, so the worker always reads fresh data from Postgres.
"""

import re
from collections import Counter

from django.db.models import Avg, Count
from django.utils import timezone

from bookings.models import Review
from summaries.models import ReviewSummary

STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "is", "was", "were", "it", "to", "of",
    "in", "on", "for", "with", "very", "my", "i", "we", "they", "this", "that",
    "be", "are", "so", "at", "as", "had", "have", "not", "too",
}  # fmt: skip


def summarise_reviews(summary_id):
    summary = ReviewSummary.objects.get(pk=summary_id)
    summary.status = ReviewSummary.Status.RUNNING
    summary.save(update_fields=["status"])

    try:
        reviews = Review.objects.filter(booking__provider_id=summary.provider_id)
        stats = reviews.aggregate(count=Count("id"), avg=Avg("rating"))

        summary.review_count = stats["count"]
        summary.average_rating = stats["avg"]
        summary.summary = build_stub_summary(
            stats["count"], stats["avg"], reviews.values_list("comment", flat=True)
        )
        summary.status = ReviewSummary.Status.DONE
    except Exception as exc:
        summary.status = ReviewSummary.Status.FAILED
        summary.error = str(exc)
        raise  # let RQ record the job as failed too
    finally:
        summary.completed_at = timezone.now()
        summary.save()


def build_stub_summary(count, avg, comments):
    """
    Stand-in for an LLM call: deterministic text from simple statistics.
    Swapping in a real model means replacing only this function.
    """
    if count == 0:
        return "No reviews yet."

    words = Counter(
        word
        for comment in comments
        for word in re.findall(r"[a-z']+", comment.lower())
        if word not in STOPWORDS and len(word) > 2
    )
    themes = ", ".join(word for word, _ in words.most_common(3)) or "no written comments"
    return f"{count} review(s), average rating {avg:.2f}/5. Common themes: {themes}."
