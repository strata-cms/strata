from uuid import uuid4

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from strata_cms.api.errors import DEFAULT_ERROR_DETAIL, public_error_detail
from strata_cms.application.errors import (
    ContentNotFoundError,
    NotAuthorizedError,
    SlugConflictError,
)
from strata_cms.domain.errors import (
    ConcurrentModificationError,
    InvalidContentTypeKeyError,
)
from strata_cms.domain.value_objects import ContentId


def test_public_detail_ignores_exception_text() -> None:
    error = ConcurrentModificationError("SELECT secret FROM internal_table")

    detail = public_error_detail(error)

    assert "SELECT" not in detail
    assert "internal_table" not in detail


def test_public_detail_omits_identifiers_and_user_supplied_values() -> None:
    content_id = ContentId(uuid4())

    assert str(content_id) not in public_error_detail(ContentNotFoundError(content_id))
    assert "private-slug" not in public_error_detail(
        SlugConflictError(parent_id=content_id, slug="private-slug")
    )
    assert "private-action" not in public_error_detail(
        NotAuthorizedError("private-action")
    )


def test_public_detail_falls_back_for_unknown_errors() -> None:
    assert public_error_detail(RuntimeError("boom /srv/app/secret.py")) == (
        DEFAULT_ERROR_DETAIL
    )


def test_public_detail_is_fixed_for_invalid_type_keys() -> None:
    first = public_error_detail(InvalidContentTypeKeyError("one"))
    second = public_error_detail(InvalidContentTypeKeyError("two"))

    assert first == second
    assert "namespaced" in first


@pytest.mark.django_db
def test_delivery_list_reports_invalid_type_key_with_fixed_detail() -> None:
    response = APIClient().get(
        reverse("api:delivery:content-list"), {"type": "Not Valid!"}
    )

    assert response.status_code == 400
    assert response.json()["detail"] == public_error_detail(
        InvalidContentTypeKeyError("")
    )


@pytest.mark.django_db
def test_management_conflict_response_does_not_echo_internal_message() -> None:
    user = get_user_model().objects.create_superuser(
        username="editor", email="editor@example.invalid", password="test-password"
    )
    client = APIClient()
    client.force_authenticate(user=user)
    missing = uuid4()

    response = client.get(reverse("api:management:content-detail", args=[missing]))

    assert response.status_code == 404
    assert str(missing) not in response.json()["detail"]
