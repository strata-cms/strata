"""Core liveness endpoint tests."""

from django.urls import reverse
from rest_framework.test import APIClient


def test_health_endpoint_is_public() -> None:
    """Health endpoint returns a minimal public liveness response."""
    client = APIClient()
    response = client.get(reverse("api:health"))

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
