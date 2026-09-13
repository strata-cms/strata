"""Django transaction-backed content Unit of Work."""

from types import TracebackType
from typing import Protocol

from django.db import transaction

from strata_cms.infrastructure.persistence.django.outbox import (
    DjangoOutboxEventPublisher,
)
from strata_cms.infrastructure.persistence.django.repositories import (
    DjangoContentRepository,
    DjangoRevisionRepository,
)


class _AtomicContext(Protocol):
    """Structural type for Django's transaction context manager."""

    def __enter__(self) -> None: ...  # pragma: no cover - protocol declaration

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None: ...  # pragma: no cover - protocol declaration


class DjangoContentUnitOfWork:
    """Keep content state, revisions, and outbox writes in one transaction."""

    def __init__(self, *, using: str = "default") -> None:
        """Wire repository/event adapters bound to one database alias."""
        self._using = using
        self.contents = DjangoContentRepository(using=using, lock_reads=True)
        self.revisions = DjangoRevisionRepository(using=using)
        self.events = DjangoOutboxEventPublisher(using=using)
        self._atomic: _AtomicContext | None = None
        self._committed = False

    def __enter__(self) -> "DjangoContentUnitOfWork":
        """Enter a Django atomic block."""
        if self._atomic is not None:
            raise RuntimeError("A Unit of Work instance cannot be entered twice.")
        self._committed = False
        self._atomic = transaction.atomic(using=self._using)
        self._atomic.__enter__()
        return self

    def commit(self) -> None:
        """Mark the current transaction for commit on successful exit."""
        if self._atomic is None:
            raise RuntimeError("Unit of Work is not active.")
        self._committed = True

    def rollback(self) -> None:
        """Mark the current transaction for rollback."""
        if self._atomic is None:
            raise RuntimeError("Unit of Work is not active.")
        transaction.set_rollback(True, using=self._using)
        self._committed = False

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Commit only explicit successful work; otherwise roll back."""
        atomic = self._atomic
        if atomic is None:  # pragma: no cover - defensive misuse guard
            raise RuntimeError("Unit of Work exit without matching enter.")

        try:
            if exc_type is not None or not self._committed:
                transaction.set_rollback(True, using=self._using)
            atomic.__exit__(exc_type, exc_value, traceback)
        finally:
            self._atomic = None
            self._committed = False
