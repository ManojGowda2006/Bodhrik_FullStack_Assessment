import django_rq
import pytest
from rq import SimpleWorker

from summaries.models import ReviewSummary

pytestmark = pytest.mark.django_db


def summarise(client, provider, capture):
    # The view enqueues on commit; run those callbacks inside the test transaction.
    with capture(execute=True):
        return client.post(f"/api/providers/{provider.id}/summarise/")


def run_worker():
    """Process queued jobs in this process (SimpleWorker doesn't fork), then stop."""
    queue = django_rq.get_queue("default")
    SimpleWorker([queue], connection=queue.connection).work(burst=True)


def test_summarise_queues_job_then_worker_completes_it(
    client_for, provider_a, customer_1, make_booking, django_capture_on_commit_callbacks
):
    make_booking(provider_a, customer_1, status="completed", rating=5, comment="punctual friendly")
    make_booking(provider_a, customer_1, status="completed", rating=3, comment="punctual rushed")
    client = client_for(provider_a)

    response = summarise(client, provider_a, django_capture_on_commit_callbacks)
    assert response.status_code == 202
    assert response.json()["status"] == "queued"
    assert django_rq.get_queue("default").count == 1  # the job is waiting in Redis

    run_worker()

    summary = client.get(f"/api/summaries/{response.json()['id']}/").json()
    assert summary["status"] == "done"
    assert summary["review_count"] == 2
    assert summary["average_rating"] == "4.00"
    assert "punctual" in summary["summary"]


def test_repeat_request_returns_in_flight_job(
    client_for, provider_a, django_capture_on_commit_callbacks
):
    client = client_for(provider_a)
    first = summarise(client, provider_a, django_capture_on_commit_callbacks).json()
    second = summarise(client, provider_a, django_capture_on_commit_callbacks).json()
    assert first["id"] == second["id"]
    assert django_rq.get_queue("default").count == 1
    assert ReviewSummary.objects.count() == 1


def test_provider_cannot_summarise_another_provider(client_for, provider_a, provider_b):
    assert (
        client_for(provider_b).post(f"/api/providers/{provider_a.id}/summarise/").status_code == 404
    )


def test_provider_sees_only_own_summaries(
    client_for, admin, provider_a, provider_b, django_capture_on_commit_callbacks
):
    summarise(client_for(admin), provider_a, django_capture_on_commit_callbacks)
    assert client_for(provider_b).get("/api/summaries/").json()["count"] == 0
    assert client_for(provider_a).get("/api/summaries/").json()["count"] == 1
