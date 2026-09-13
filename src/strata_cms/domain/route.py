"""Optional tree position attached to routable content.

Page hierarchy/routing is a page *capability*, not a field every Content item
carries: a route only exists for content that explicitly attaches one.
Cross-node invariants (cycles, sibling slug uniqueness) need the repository
and are therefore enforced by the application use case, not here.
"""

import re
from dataclasses import dataclass, replace
from typing import Self

from strata_cms.domain.errors import InvalidSlugError
from strata_cms.domain.value_objects import ContentId

_SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
MAX_SLUG_LENGTH = 200


@dataclass(frozen=True, slots=True)
class ContentRoute:
    """One node's tree position: parent pointer plus its slug segment."""

    content_id: ContentId
    parent_id: ContentId | None
    slug: str
    version: int = 0

    def __post_init__(self) -> None:
        """Validate slug shape and reject a node parented to itself."""
        if len(self.slug) > MAX_SLUG_LENGTH or not _SLUG.fullmatch(self.slug):
            raise InvalidSlugError(
                "Slugs must be <= 200 chars, lowercase alphanumeric segments "
                "separated by single hyphens, e.g. 'about-us'."
            )
        if self.parent_id == self.content_id:
            raise InvalidSlugError("A route cannot be parented to itself.")

    def moved_to(self, *, parent_id: ContentId | None, slug: str) -> Self:
        """Return the route repositioned under a new parent/slug."""
        return replace(self, parent_id=parent_id, slug=slug, version=self.version + 1)
