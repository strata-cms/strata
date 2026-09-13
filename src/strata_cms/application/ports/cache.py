"""Minimal cache port; prefer semantic cache services above this interface."""

from datetime import timedelta
from typing import Protocol


class Cache(Protocol):
    """Store disposable cached values without exposing provider primitives."""

    def get(self, key: str) -> object | None:
        """Return a cached value or ``None`` when absent."""
        ...  # pragma: no cover - protocol declaration

    def set(
        self,
        key: str,
        value: object,
        *,
        ttl: timedelta | None = None,
    ) -> None:
        """Store a value for an optional time-to-live."""
        ...  # pragma: no cover - protocol declaration

    def delete(self, key: str) -> None:
        """Remove a cached value if present."""
        ...  # pragma: no cover - protocol declaration
