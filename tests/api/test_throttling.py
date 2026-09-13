from unittest.mock import patch

import pytest
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework.throttling import ScopedRateThrottle

pytestmark = pytest.mark.django_db


def test_delivery_api_throttles_after_configured_rate() -> None:
    client = APIClient()
    url = reverse("api:delivery:content-list")

    with patch.dict(ScopedRateThrottle.THROTTLE_RATES, {"strata-delivery": "2/min"}):
        first = client.get(url)
        second = client.get(url)
        third = client.get(url)

    assert first.status_code == 200
    assert second.status_code == 200
    assert third.status_code == 429


def test_delivery_api_allows_requests_under_the_configured_rate() -> None:
    client = APIClient()
    url = reverse("api:delivery:content-list")

    with patch.dict(ScopedRateThrottle.THROTTLE_RATES, {"strata-delivery": "1000/min"}):
        responses = [client.get(url) for _ in range(5)]

    assert all(response.status_code == 200 for response in responses)
