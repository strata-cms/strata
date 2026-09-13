from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from strata_cms.application.ports.search import SearchQuery
from strata_cms.config.services import dispatch_content_event, get_search_backend
from strata_cms.examples.simple_article import EXAMPLE_CONTENT_TYPE
from strata_cms.infrastructure.persistence.django.outbox import DjangoOutboxQueue
from strata_cms.infrastructure.tasks.worker import run_worker_batch

pytestmark = pytest.mark.django_db


def _staff_client() -> APIClient:
    user_model = get_user_model()
    user = user_model.objects.create_superuser(
        username="editor",
        email="editor@example.invalid",
        password="test-password",
    )
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def test_worker_dispatcher_indexes_content_after_publish() -> None:
    staff = _staff_client()
    create = staff.post(
        reverse("api:management:content-create"),
        {
            "type": str(EXAMPLE_CONTENT_TYPE),
            "schema_version": 2,
            "data": {"title": "Bengal cats", "body": "Purr a lot"},
        },
        format="json",
    )
    created = create.json()
    staff.post(
        reverse("api:management:content-publish", args=[created["content_id"]]),
        {
            "expected_version": created["content_version"],
            "revision_id": created["revision_id"],
        },
        format="json",
    )

    queue = DjangoOutboxQueue(worker_id="test-worker")
    processed = run_worker_batch(
        queue,
        dispatch=dispatch_content_event,
        visibility_timeout=timedelta(seconds=30),
    )

    assert processed == 1
    result = get_search_backend().search(SearchQuery(text="Bengal"))
    assert result.total == 1
    assert str(result.hits[0].document_id) == created["content_id"]


def test_worker_dispatcher_removes_content_after_archive() -> None:
    staff = _staff_client()
    create = staff.post(
        reverse("api:management:content-create"),
        {
            "type": str(EXAMPLE_CONTENT_TYPE),
            "schema_version": 2,
            "data": {"title": "Siberian huskies", "body": "Fluffy"},
        },
        format="json",
    )
    created = create.json()
    publish = staff.post(
        reverse("api:management:content-publish", args=[created["content_id"]]),
        {
            "expected_version": created["content_version"],
            "revision_id": created["revision_id"],
        },
        format="json",
    )

    queue = DjangoOutboxQueue(worker_id="test-worker")
    run_worker_batch(
        queue,
        dispatch=dispatch_content_event,
        visibility_timeout=timedelta(seconds=30),
    )

    staff.post(
        reverse("api:management:content-archive", args=[created["content_id"]]),
        {"expected_version": publish.json()["content_version"]},
        format="json",
    )
    run_worker_batch(
        queue,
        dispatch=dispatch_content_event,
        visibility_timeout=timedelta(seconds=30),
    )

    result = get_search_backend().search(SearchQuery(text="huskies"))
    assert result.total == 0
