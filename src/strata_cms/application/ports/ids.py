"""Identifier-generation port."""

from typing import Protocol
from uuid import UUID


class IdGenerator(Protocol):
    """Generate opaque stable UUID identities at application boundaries."""

    def new_uuid(self) -> UUID:
        """Return a new UUID."""
        ...  # pragma: no cover - protocol declaration
