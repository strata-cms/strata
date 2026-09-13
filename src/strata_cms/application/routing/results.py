"""Stable result DTOs returned by content route write use cases."""

from dataclasses import dataclass

from strata_cms.domain.value_objects import ContentId


@dataclass(frozen=True, slots=True)
class RouteResult:
    """Identity/position resulting from a successful route mutation."""

    content_id: ContentId
    parent_id: ContentId | None
    slug: str
    version: int
    path: str
