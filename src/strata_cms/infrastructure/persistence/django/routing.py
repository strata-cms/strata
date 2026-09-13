"""Django persistence adapters for the content route tree and path projection."""

from types import TracebackType
from typing import Protocol

from django.db import transaction

from strata_cms.domain.errors import ConcurrentModificationError
from strata_cms.domain.route import ContentRoute
from strata_cms.domain.value_objects import ContentId
from strata_cms.infrastructure.persistence.django.models import (
    ContentRouteRecord,
    RoutePathRecord,
)


def _route_from_record(record: ContentRouteRecord) -> ContentRoute:
    return ContentRoute(
        content_id=ContentId(record.content_id),
        parent_id=ContentId(record.parent_id) if record.parent_id is not None else None,
        slug=record.slug,
        version=record.version,
    )


class DjangoContentRouteRepository:
    """Persist and rehydrate content route tree nodes."""

    def __init__(self, *, using: str = "default") -> None:
        """Bind the adapter to a Django database alias."""
        self._using = using

    def get(self, content_id: ContentId) -> ContentRoute | None:
        """Return the route attached to one content item, if any."""
        record = (
            ContentRouteRecord.objects.using(self._using).filter(pk=content_id).first()
        )
        return _route_from_record(record) if record is not None else None

    def get_by_parent_and_slug(
        self,
        parent_id: ContentId | None,
        slug: str,
    ) -> ContentRoute | None:
        """Return the sibling route already using this parent/slug, if any."""
        record = (
            ContentRouteRecord.objects.using(self._using)
            .filter(parent_id=parent_id, slug=slug)
            .first()
        )
        return _route_from_record(record) if record is not None else None

    def list_children(self, parent_id: ContentId | None) -> tuple[ContentRoute, ...]:
        """Return the direct children of one node (or the roots, if None)."""
        records = (
            ContentRouteRecord.objects.using(self._using)
            .filter(parent_id=parent_id)
            .order_by("slug")
        )
        return tuple(_route_from_record(record) for record in records)

    def add(self, route: ContentRoute) -> None:
        """Insert a new route at version zero."""
        ContentRouteRecord.objects.using(self._using).create(
            content_id=route.content_id,
            parent_id=route.parent_id,
            slug=route.slug,
            version=route.version,
        )

    def update(self, route: ContentRoute, *, expected_version: int) -> None:
        """Persist a moved/renamed route using optimistic compare-and-swap."""
        updated = (
            ContentRouteRecord.objects.using(self._using)
            .filter(pk=route.content_id, version=expected_version)
            .update(parent_id=route.parent_id, slug=route.slug, version=route.version)
        )
        if updated != 1:
            raise ConcurrentModificationError(
                f"Route for '{route.content_id}' changed since version "
                f"{expected_version}."
            )

    def delete(self, content_id: ContentId) -> None:
        """Remove a route; callers must ensure it has no children first."""
        ContentRouteRecord.objects.using(self._using).filter(pk=content_id).delete()


class DjangoRoutePathProjection:
    """Rebuildable `path -> content_id` projection used by the Delivery API."""

    def __init__(self, *, using: str = "default") -> None:
        """Bind the adapter to a Django database alias."""
        self._using = using

    def set_path(self, content_id: ContentId, path: str) -> None:
        """Insert or replace the projected path for one content item."""
        RoutePathRecord.objects.using(self._using).update_or_create(
            content_id=content_id,
            defaults={"path": path},
        )

    def remove(self, content_id: ContentId) -> None:
        """Remove the projected path for one content item, if present."""
        RoutePathRecord.objects.using(self._using).filter(pk=content_id).delete()

    def resolve(self, path: str) -> ContentId | None:
        """Return the content item currently projected at this exact path."""
        record = RoutePathRecord.objects.using(self._using).filter(path=path).first()
        return ContentId(record.content_id) if record is not None else None


class _AtomicContext(Protocol):
    """Structural type for Django's transaction context manager."""

    def __enter__(self) -> None: ...  # pragma: no cover - protocol declaration

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None: ...  # pragma: no cover - protocol declaration


class DjangoRouteUnitOfWork:
    """Keep route and path-projection writes in one transaction."""

    def __init__(self, *, using: str = "default") -> None:
        """Wire repository/projection adapters bound to one database alias."""
        self._using = using
        self.routes = DjangoContentRouteRepository(using=using)
        self.paths = DjangoRoutePathProjection(using=using)
        self._atomic: _AtomicContext | None = None
        self._committed = False

    def __enter__(self) -> "DjangoRouteUnitOfWork":
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
