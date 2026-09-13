"""Transaction boundary port for application use cases."""

from types import TracebackType
from typing import Protocol, Self


class UnitOfWork(Protocol):
    """Own a use-case transaction; concrete units expose needed repositories."""

    def __enter__(self) -> Self:
        """Begin the unit-of-work scope."""
        ...  # pragma: no cover - protocol declaration

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Roll back uncommitted work and release resources."""
        ...  # pragma: no cover - protocol declaration

    def commit(self) -> None:
        """Commit all authoritative writes in the unit of work atomically."""
        ...  # pragma: no cover - protocol declaration

    def rollback(self) -> None:
        """Roll back all writes in the unit of work."""
        ...  # pragma: no cover - protocol declaration
