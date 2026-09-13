"""Tests for simple provider-neutral default infrastructure adapters."""

from datetime import timedelta

from django.utils import timezone

from strata_cms.infrastructure.cache.django import DjangoCache
from strata_cms.infrastructure.clock.system import DjangoClock


def test_django_clock_returns_timezone_aware_timestamp() -> None:
    """The default clock must be safe for timezone-aware application logic."""
    now = DjangoClock().now()

    assert timezone.is_aware(now)


def test_django_cache_round_trip() -> None:
    """The Django cache adapter implements the baseline cache semantics."""
    cache = DjangoCache()
    key = "tests:infrastructure:cache"

    cache.set(key, {"status": "ok"}, ttl=timedelta(minutes=1))

    assert cache.get(key) == {"status": "ok"}
    cache.delete(key)
    assert cache.get(key) is None
