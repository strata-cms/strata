import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from strata_cms.examples.simple_article import EXAMPLE_CONTENT_TYPE
from strata_cms.infrastructure.persistence.django.models import ContentRecord

pytestmark = pytest.mark.django_db


def _admin_client() -> Client:
    user_model = get_user_model()
    user = user_model.objects.create_superuser(
        username="admin",
        email="admin@example.invalid",
        password="test-password",
    )
    client = Client()
    client.force_login(user)
    return client


def test_admin_add_view_uses_content_type_chooser_and_schema_editor() -> None:
    client = _admin_client()
    url = reverse("admin:strata_persistence_contentrecord_add")

    chooser = client.get(url)
    editor = client.get(url, {"type": str(EXAMPLE_CONTENT_TYPE)})

    assert chooser.status_code == 200
    assert b"Choose content type" in chooser.content
    assert editor.status_code == 200
    assert b"cms-editor-schema" in editor.content
    assert b"Save revision" in editor.content


def test_admin_change_redirects_away_from_django_model_form() -> None:
    client = _admin_client()
    record = ContentRecord.objects.create(
        type_key=str(EXAMPLE_CONTENT_TYPE),
        created_at=timezone.now(),
        created_by="test",
    )
    change_url = reverse(
        "admin:strata_persistence_contentrecord_change",
        args=[record.pk],
    )

    response = client.get(change_url)

    assert response.status_code == 302
    assert response.headers["Location"].endswith(f"/{record.pk}/editor/")
