"""Route-specific Unit of Work contract."""

from typing import Protocol

from strata_cms.application.ports.routing import (
    ContentRouteRepository,
    RoutePathProjection,
)
from strata_cms.application.ports.unit_of_work import UnitOfWork


class RouteUnitOfWork(UnitOfWork, Protocol):
    """Atomic persistence boundary required by route write use cases."""

    @property
    def routes(self) -> ContentRouteRepository:
        """Return the content route repository for this transaction."""
        ...  # pragma: no cover - protocol declaration

    @property
    def paths(self) -> RoutePathProjection:
        """Return the rebuildable path projection for this transaction."""
        ...  # pragma: no cover - protocol declaration
