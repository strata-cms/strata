"""Shared pytest fixtures for the whole suite."""

import pytest
from django.core.cache import cache


@pytest.fixture(autouse=True)
def _clear_django_cache() -> None:
    """Isolate tests from Django's process-wide default cache backend."""
    cache.clear()
