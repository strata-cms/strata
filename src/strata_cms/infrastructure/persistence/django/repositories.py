"""Django ORM repository implementations for content/revisions."""

from strata_cms.domain.content import Content
from strata_cms.domain.errors import ConcurrentModificationError
from strata_cms.domain.revision import Revision
from strata_cms.domain.value_objects import ContentId, RevisionId
from strata_cms.infrastructure.persistence.django.mappers import (
    content_from_record,
    revision_from_record,
)
from strata_cms.infrastructure.persistence.django.models import (
    ContentRecord,
    RevisionRecord,
)


class DjangoContentRepository:
    """Persist Content aggregates using compare-and-swap version updates."""

    def __init__(
        self,
        *,
        using: str = "default",
        lock_reads: bool = False,
    ) -> None:
        """Bind the adapter to a Django database alias and locking policy."""
        self._using = using
        self._lock_reads = lock_reads

    def get(self, content_id: ContentId) -> Content | None:
        """Load an aggregate without leaking the persistence record."""
        query = ContentRecord.objects.using(self._using).filter(pk=content_id)
        if self._lock_reads:
            query = query.select_for_update()
        record = query.first()
        return content_from_record(record) if record is not None else None

    def add(self, content: Content) -> None:
        """Insert a new version-zero aggregate shell."""
        if content.version != 0 or content.latest_revision_id is not None:
            raise ValueError("New Content must be persisted before its first revision.")

        ContentRecord.objects.using(self._using).create(
            id=content.id,
            type_key=str(content.type_key),
            created_at=content.created_at,
            created_by=str(content.created_by),
            latest_revision_number=0,
            version=0,
        )

    def update(self, content: Content, *, expected_version: int) -> None:
        """Atomically persist aggregate pointers only if version is unchanged."""
        updated = (
            ContentRecord.objects.using(self._using)
            .filter(pk=content.id, version=expected_version)
            .update(
                latest_revision_id=content.latest_revision_id,
                latest_revision_number=content.latest_revision_number,
                published_revision_id=content.published_revision_id,
                published_at=content.published_at,
                published_by=(
                    str(content.published_by)
                    if content.published_by is not None
                    else None
                ),
                archived_at=content.archived_at,
                archived_by=(
                    str(content.archived_by)
                    if content.archived_by is not None
                    else None
                ),
                version=content.version,
            )
        )
        if updated != 1:
            raise ConcurrentModificationError(
                f"Content '{content.id}' changed since version {expected_version}."
            )


class DjangoRevisionRepository:
    """Append-only Django repository for immutable revisions."""

    def __init__(self, *, using: str = "default") -> None:
        """Bind the adapter to a Django database alias."""
        self._using = using

    def get(self, revision_id: RevisionId) -> Revision | None:
        """Load one immutable revision."""
        record = (
            RevisionRecord.objects.using(self._using).filter(pk=revision_id).first()
        )
        return revision_from_record(record) if record is not None else None

    def add(self, revision: Revision) -> None:
        """Append a revision; revisions are never updated in place."""
        RevisionRecord.objects.using(self._using).create(
            id=revision.id,
            content_id=revision.content_id,
            number=revision.number,
            content_type_key=str(revision.content_type),
            schema_version=revision.schema_version,
            data=revision.data.as_dict(),
            created_at=revision.created_at,
            created_by=str(revision.created_by),
        )
