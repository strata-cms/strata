"""Content-specific Unit of Work contract."""

from typing import Protocol

from strata_cms.application.ports.events import EventPublisher
from strata_cms.application.ports.unit_of_work import UnitOfWork
from strata_cms.domain.repositories import ContentRepository, RevisionRepository


class ContentUnitOfWork(UnitOfWork, Protocol):
    """Atomic persistence boundary required by content write use cases."""

    @property
    def contents(self) -> ContentRepository:
        """Return the content aggregate repository for this transaction."""
        ...  # pragma: no cover - protocol declaration

    @property
    def revisions(self) -> RevisionRepository:
        """Return the immutable revision repository for this transaction."""
        ...  # pragma: no cover - protocol declaration

    @property
    def events(self) -> EventPublisher:
        """Return the integration-event publisher for this transaction."""
        ...  # pragma: no cover - protocol declaration
