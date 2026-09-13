"""Read-side application port for published Delivery API content."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from strata_cms.domain.revision import Revision
from strata_cms.domain.value_objects import ContentId, ContentTypeKey


@dataclass(frozen=True, slots=True)
class PublishedRevision:
    """Published pointer plus its immutable revision snapshot."""

    content_id: ContentId
    type_key: ContentTypeKey
    revision: Revision
    published_at: datetime


class ContentDeliveryQueries(Protocol):
    """Load published revisions for the public Delivery API."""

    def get_published(self, content_id: ContentId) -> PublishedRevision | None:
        """Return the published pointer/snapshot, or ``None`` when unpublished."""
        ...  # pragma: no cover - protocol declaration

    def list_published(
        self,
        *,
        type_key: ContentTypeKey | None,
        limit: int,
        offset: int,
    ) -> tuple[Sequence[PublishedRevision], int]:
        """Return one page of published content, newest-published first.

        Returns the page items plus the total matching count (for pagination
        metadata), optionally filtered to one content type.
        """
        ...  # pragma: no cover - protocol declaration
