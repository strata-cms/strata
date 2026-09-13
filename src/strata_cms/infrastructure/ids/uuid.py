"""System UUID generator."""

from uuid import UUID, uuid4


class Uuid4Generator:
    """Generate random RFC 4122 UUIDv4 identifiers."""

    def new_uuid(self) -> UUID:
        """Return a new random UUID."""
        return uuid4()
