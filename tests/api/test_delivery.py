from uuid import UUID

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from strata_cms.application.ports.search import SearchDocument
from strata_cms.config.services import get_search_backend
from strata_cms.examples.simple_article import EXAMPLE_CONTENT_TYPE

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


def test_delivery_api_404s_for_unpublished_content() -> None:
    staff = _staff_client()
    create = staff.post(
        reverse("api:management:content-create"),
        {
            "type": str(EXAMPLE_CONTENT_TYPE),
            "schema_version": 2,
            "data": {"title": "Draft only", "body": "Body"},
        },
        format="json",
    )
    assert create.status_code == 201
    content_id = create.json()["content_id"]

    anonymous = APIClient()
    response = anonymous.get(reverse("api:delivery:content-detail", args=[content_id]))

    assert response.status_code == 404


def test_delivery_api_returns_published_revision_to_anonymous_clients() -> None:
    staff = _staff_client()
    create = staff.post(
        reverse("api:management:content-create"),
        {
            "type": str(EXAMPLE_CONTENT_TYPE),
            "schema_version": 2,
            "data": {"title": "Published", "body": "Body"},
        },
        format="json",
    )
    created = create.json()
    content_id = created["content_id"]

    staff.post(
        reverse("api:management:content-publish", args=[content_id]),
        {
            "expected_version": 1,
            "revision_id": created["revision_id"],
        },
        format="json",
    )

    revision = staff.post(
        reverse("api:management:content-revision-create", args=[content_id]),
        {
            "expected_version": 2,
            "schema_version": 2,
            "data": {"title": "Draft edit", "body": "Not yet public"},
        },
        format="json",
    )
    assert revision.status_code == 201

    anonymous = APIClient()
    response = anonymous.get(reverse("api:delivery:content-detail", args=[content_id]))

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["title"] == "Published"
    assert body["revision_id"] == created["revision_id"]


def test_delivery_api_404s_for_archived_content_even_if_published() -> None:
    staff = _staff_client()
    create = staff.post(
        reverse("api:management:content-create"),
        {
            "type": str(EXAMPLE_CONTENT_TYPE),
            "schema_version": 2,
            "data": {"title": "Published then archived", "body": "Body"},
        },
        format="json",
    )
    created = create.json()
    content_id = created["content_id"]

    publish = staff.post(
        reverse("api:management:content-publish", args=[content_id]),
        {
            "expected_version": created["content_version"],
            "revision_id": created["revision_id"],
        },
        format="json",
    )
    assert publish.status_code == 200

    archive = staff.post(
        reverse("api:management:content-archive", args=[content_id]),
        {"expected_version": publish.json()["content_version"]},
        format="json",
    )
    assert archive.status_code == 200

    anonymous = APIClient()
    response = anonymous.get(reverse("api:delivery:content-detail", args=[content_id]))

    assert response.status_code == 404


def _publish(staff: APIClient, *, title: str) -> dict[str, object]:
    create = staff.post(
        reverse("api:management:content-create"),
        {
            "type": str(EXAMPLE_CONTENT_TYPE),
            "schema_version": 2,
            "data": {"title": title, "body": "Body"},
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
    assert isinstance(created, dict)
    return created


def test_delivery_list_returns_only_published_non_archived_content() -> None:
    staff = _staff_client()
    published = _publish(staff, title="Published item")
    draft = staff.post(
        reverse("api:management:content-create"),
        {
            "type": str(EXAMPLE_CONTENT_TYPE),
            "schema_version": 2,
            "data": {"title": "Draft item", "body": "Body"},
        },
        format="json",
    ).json()
    archived = _publish(staff, title="Archived item")
    staff.post(
        reverse("api:management:content-archive", args=[archived["content_id"]]),
        {"expected_version": 2},
        format="json",
    )

    anonymous = APIClient()
    response = anonymous.get(reverse("api:delivery:content-list"))

    assert response.status_code == 200
    body = response.json()
    ids = {item["content_id"] for item in body["results"]}
    assert published["content_id"] in ids
    assert draft["content_id"] not in ids
    assert archived["content_id"] not in ids


def test_delivery_list_filters_by_type_and_paginates() -> None:
    staff = _staff_client()
    for i in range(3):
        _publish(staff, title=f"Item {i}")

    params: dict[str, str | int] = {
        "type": str(EXAMPLE_CONTENT_TYPE),
        "limit": 2,
        "offset": 0,
    }
    anonymous = APIClient()
    response = anonymous.get(reverse("api:delivery:content-list"), params)

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 3
    assert body["limit"] == 2
    assert body["offset"] == 0
    assert len(body["results"]) == 2


def test_delivery_list_rejects_unknown_type_key() -> None:
    anonymous = APIClient()

    response = anonymous.get(
        reverse("api:delivery:content-list"),
        {"type": "not a valid key"},
    )

    assert response.status_code == 400


def test_delivery_detail_serves_stale_cache_within_ttl() -> None:
    staff = _staff_client()
    created = _publish(staff, title="Cached title")
    content_id = created["content_id"]
    anonymous = APIClient()
    first = anonymous.get(reverse("api:delivery:content-detail", args=[content_id]))
    assert first.status_code == 200
    assert first.json()["data"]["title"] == "Cached title"

    staff.post(
        reverse("api:management:content-revision-create", args=[content_id]),
        {
            "expected_version": 2,
            "schema_version": 2,
            "data": {"title": "New title", "body": "Body"},
        },
        format="json",
    )
    staff.post(
        reverse("api:management:content-publish", args=[content_id]),
        {"expected_version": 3, "revision_id": created["revision_id"]},
        format="json",
    )

    second = anonymous.get(reverse("api:delivery:content-detail", args=[content_id]))
    assert second.status_code == 200
    assert second.json()["data"]["title"] == "Cached title"


def test_search_finds_indexed_content() -> None:
    get_search_backend().index(
        SearchDocument(
            id=UUID(int=1),
            text="Bengal cats are wonderful companions",
            fields={"type": str(EXAMPLE_CONTENT_TYPE)},
        )
    )

    anonymous = APIClient()
    response = anonymous.get(reverse("api:delivery:content-search"), {"q": "Bengal"})

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 1
    assert body["results"][0]["content_id"] == str(UUID(int=1))


def test_search_requires_a_query_string() -> None:
    anonymous = APIClient()

    response = anonymous.get(reverse("api:delivery:content-search"))

    assert response.status_code == 400


def test_search_rejects_unknown_type_filter() -> None:
    anonymous = APIClient()

    response = anonymous.get(
        reverse("api:delivery:content-search"),
        {"q": "cats", "type": "not a valid key"},
    )

    assert response.status_code == 400


def test_publishing_content_does_not_appear_in_search_until_indexed() -> None:
    staff = _staff_client()
    _publish(staff, title="Not yet searchable")

    anonymous = APIClient()
    response = anonymous.get(
        reverse("api:delivery:content-search"), {"q": "searchable"}
    )

    assert response.status_code == 200
    assert response.json()["count"] == 0
