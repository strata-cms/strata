"""Commands for content route mutation use cases."""

from dataclasses import dataclass

from strata_cms.domain.value_objects import ContentId


@dataclass(frozen=True, slots=True)
class AttachRoute:
    """Attach a new route to content that has none yet."""

    content_id: ContentId
    parent_id: ContentId | None
    slug: str


@dataclass(frozen=True, slots=True)
class MoveRoute:
    """Move/rename an existing route using optimistic concurrency."""

    content_id: ContentId
    parent_id: ContentId | None
    slug: str
    expected_version: int


@dataclass(frozen=True, slots=True)
class DetachRoute:
    """Remove a childless route using optimistic concurrency."""

    content_id: ContentId
    expected_version: int
