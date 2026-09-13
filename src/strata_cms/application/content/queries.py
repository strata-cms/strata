"""Read-side DTOs for management/editor content access."""

from dataclasses import dataclass
from datetime import datetime

from strata_cms.domain.revision import RevisionData
from strata_cms.domain.value_objects import (
    ActorId,
    ContentId,
    ContentTypeKey,
    RevisionId,
)


@dataclass(frozen=True, slots=True)
class EditableContent:
    """Latest working revision plus concurrency metadata for an editor client."""

    content_id: ContentId
    type_key: ContentTypeKey
    content_version: int
    revision_id: RevisionId
    revision_number: int
    schema_version: int
    data: RevisionData
    published_revision_id: RevisionId | None
    is_archived: bool


@dataclass(frozen=True, slots=True)
class RevisionSummary:
    """Lightweight revision history entry, without the full data payload."""

    revision_id: RevisionId
    number: int
    schema_version: int
    created_at: datetime
    created_by: ActorId
    is_published: bool
