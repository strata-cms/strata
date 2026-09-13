"""Default cache adapter backed by Django's configured cache framework."""

from datetime import timedelta
from typing import TYPE_CHECKING

from django.core.cache import caches

if TYPE_CHECKING:
    from django.core.cache.backends.base import BaseCache


class DjangoCache:
    """Adapt a configured Django cache alias to the CMS cache port."""

    def __init__(self, alias: str = "default") -> None:
        """Bind the adapter to one configured Django cache alias."""
        self._cache: BaseCache = caches[alias]

    def get(self, key: str) -> object | None:
        """Return a cached value or ``None`` when absent."""
        value: object | None = self._cache.get(key)
        return value

    def set(
        self,
        key: str,
        value: object,
        *,
        ttl: timedelta | None = None,
    ) -> None:
        """Store a value with an optional TTL."""
        timeout = None if ttl is None else ttl.total_seconds()
        self._cache.set(key, value, timeout=timeout)

    def delete(self, key: str) -> None:
        """Delete a cache key when present."""
        self._cache.delete(key)
