"""Explicit mapping between Django records and persistence-ignorant entities."""

from strata_cms.domain.content import Content
from strata_cms.domain.revision import Revision, RevisionData
from strata_cms.domain.value_objects import (
    ActorId,
    ContentId,
    ContentTypeKey,
    RevisionId,
)
from strata_cms.infrastructure.persistence.django.models import (
    ContentRecord,
    RevisionRecord,
)


def content_from_record(record: ContentRecord) -> Content:
    """Rehydrate a Content aggregate without exposing a Django model."""
    return Content(
        id=ContentId(record.id),
        type_key=ContentTypeKey(record.type_key),
        created_at=record.created_at,
        created_by=ActorId(record.created_by),
        latest_revision_id=(
            RevisionId(record.latest_revision_id)
            if record.latest_revision_id is not None
            else None
        ),
        latest_revision_number=record.latest_revision_number,
        published_revision_id=(
            RevisionId(record.published_revision_id)
            if record.published_revision_id is not None
            else None
        ),
        published_at=record.published_at,
        published_by=(
            ActorId(record.published_by) if record.published_by is not None else None
        ),
        archived_at=record.archived_at,
        archived_by=(
            ActorId(record.archived_by) if record.archived_by is not None else None
        ),
        version=record.version,
    )


def revision_from_record(record: RevisionRecord) -> Revision:
    """Rehydrate an immutable Revision from a Django record."""
    if not isinstance(record.data, dict):
        raise ValueError("Persisted revision data root must be a JSON object.")

    return Revision(
        id=RevisionId(record.id),
        content_id=ContentId(record.content_id),
        number=record.number,
        content_type=ContentTypeKey(record.content_type_key),
        schema_version=record.schema_version,
        data=RevisionData.from_mapping(record.data),
        created_at=record.created_at,
        created_by=ActorId(record.created_by),
    )
