"""API schema endpoint tests."""

from django.urls import reverse
from rest_framework.test import APIClient


def test_openapi_schema_is_available() -> None:
    """Schema endpoint exposes the generated OpenAPI document."""
    client = APIClient()

    response = client.get(reverse("api-schema"))

    assert response.status_code == 200
    assert response["Content-Type"].startswith("application/vnd.oai.openapi")
