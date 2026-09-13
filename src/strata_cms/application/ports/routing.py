"""Application-owned ports for the content route tree and path projection."""

from typing import Protocol

from strata_cms.domain.route import ContentRoute
from strata_cms.domain.value_objects import ContentId


class ContentRouteRepository(Protocol):
    """Persist and rehydrate content route tree nodes."""

    def get(self, content_id: ContentId) -> ContentRoute | None:
        """Return the route attached to one content item, if any."""
        ...  # pragma: no cover - protocol declaration

    def get_by_parent_and_slug(
        self,
        parent_id: ContentId | None,
        slug: str,
    ) -> ContentRoute | None:
        """Return the sibling route already using this parent/slug, if any."""
        ...  # pragma: no cover - protocol declaration

    def list_children(self, parent_id: ContentId | None) -> tuple[ContentRoute, ...]:
        """Return the direct children of one node (or the roots, if None)."""
        ...  # pragma: no cover - protocol declaration

    def add(self, route: ContentRoute) -> None:
        """Insert a new route at version zero."""
        ...  # pragma: no cover - protocol declaration

    def update(self, route: ContentRoute, *, expected_version: int) -> None:
        """Persist a moved/renamed route using optimistic compare-and-swap."""
        ...  # pragma: no cover - protocol declaration

    def delete(self, content_id: ContentId) -> None:
        """Remove a route; callers must ensure it has no children first."""
        ...  # pragma: no cover - protocol declaration


class RoutePathProjection(Protocol):
    """Rebuildable `path -> content_id` projection used by the Delivery API.

    Purely structural: it says nothing about publish state. Resolving a path
    to delivery-ready content still goes through the normal published-content
    read path, so drafts are never leaked through routing.
    """

    def set_path(self, content_id: ContentId, path: str) -> None:
        """Insert or replace the projected path for one content item."""
        ...  # pragma: no cover - protocol declaration

    def remove(self, content_id: ContentId) -> None:
        """Remove the projected path for one content item, if present."""
        ...  # pragma: no cover - protocol declaration

    def resolve(self, path: str) -> ContentId | None:
        """Return the content item currently projected at this exact path."""
        ...  # pragma: no cover - protocol declaration
