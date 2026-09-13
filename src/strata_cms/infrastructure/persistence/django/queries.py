"""Django-optimized read queries for management content editing and delivery."""

from collections.abc import Sequence

from strata_cms.application.content.queries import EditableContent, RevisionSummary
from strata_cms.application.ports.content_delivery import PublishedRevision
from strata_cms.domain.revision import RevisionData
from strata_cms.domain.value_objects import (
    ActorId,
    ContentId,
    ContentTypeKey,
    RevisionId,
)
from strata_cms.infrastructure.persistence.django.mappers import revision_from_record
from strata_cms.infrastructure.persistence.django.models import (
    ContentRecord,
    RevisionRecord,
)


class DjangoContentEditorQueries:
    """Read current editor state without hydrating a write aggregate."""

    def __init__(self, *, using: str = "default") -> None:
        """Bind the adapter to a Django database alias."""
        self._using = using

    def get_latest(self, content_id: ContentId) -> EditableContent | None:
        """Fetch one content shell and latest immutable revision efficiently."""
        record = (
            ContentRecord.objects.using(self._using)
            .select_related("latest_revision", "published_revision")
            .filter(pk=content_id)
            .first()
        )
        if record is None or record.latest_revision is None:
            return None
        revision = record.latest_revision
        return EditableContent(
            content_id=ContentId(record.id),
            type_key=ContentTypeKey(record.type_key),
            content_version=record.version,
            revision_id=RevisionId(revision.id),
            revision_number=revision.number,
            schema_version=revision.schema_version,
            data=RevisionData.from_mapping(revision.data),
            published_revision_id=(
                RevisionId(record.published_revision_id)
                if record.published_revision_id is not None
                else None
            ),
            is_archived=record.archived_at is not None,
        )

    def list_revisions(self, content_id: ContentId) -> tuple[RevisionSummary, ...]:
        """Fetch every revision's history metadata for one content item."""
        content = (
            ContentRecord.objects.using(self._using)
            .filter(pk=content_id)
            .values("published_revision_id")
            .first()
        )
        if content is None:
            return ()
        published_revision_id = content["published_revision_id"]
        records = (
            RevisionRecord.objects.using(self._using)
            .filter(content_id=content_id)
            .order_by("-number")
        )
        return tuple(
            RevisionSummary(
                revision_id=RevisionId(record.id),
                number=record.number,
                schema_version=record.schema_version,
                created_at=record.created_at,
                created_by=ActorId(record.created_by),
                is_published=record.id == published_revision_id,
            )
            for record in records
        )

    def get_revision(
        self,
        content_id: ContentId,
        revision_id: RevisionId,
    ) -> EditableContent | None:
        """Fetch one historical revision, scoped to its owning content item."""
        content = ContentRecord.objects.using(self._using).filter(pk=content_id).first()
        if content is None:
            return None
        revision = (
            RevisionRecord.objects.using(self._using)
            .filter(content_id=content_id, pk=revision_id)
            .first()
        )
        if revision is None:
            return None
        return EditableContent(
            content_id=ContentId(content.id),
            type_key=ContentTypeKey(content.type_key),
            content_version=content.version,
            revision_id=RevisionId(revision.id),
            revision_number=revision.number,
            schema_version=revision.schema_version,
            data=RevisionData.from_mapping(revision.data),
            published_revision_id=(
                RevisionId(content.published_revision_id)
                if content.published_revision_id is not None
                else None
            ),
            is_archived=content.archived_at is not None,
        )


class DjangoContentDeliveryQueries:
    """Read the currently published revision without hydrating a write aggregate."""

    def __init__(self, *, using: str = "default") -> None:
        """Bind the adapter to a Django database alias."""
        self._using = using

    def get_published(self, content_id: ContentId) -> PublishedRevision | None:
        """Fetch the published pointer and its immutable revision, if any."""
        record = (
            ContentRecord.objects.using(self._using)
            .select_related("published_revision")
            .filter(pk=content_id)
            .first()
        )
        if (
            record is None
            or record.published_revision is None
            or record.published_at is None
            or record.archived_at is not None
        ):
            return None
        return PublishedRevision(
            content_id=ContentId(record.id),
            type_key=ContentTypeKey(record.type_key),
            revision=revision_from_record(record.published_revision),
            published_at=record.published_at,
        )

    def list_published(
        self,
        *,
        type_key: ContentTypeKey | None,
        limit: int,
        offset: int,
    ) -> tuple[Sequence[PublishedRevision], int]:
        """Fetch one page of published, non-archived content, newest first."""
        queryset = (
            ContentRecord.objects.using(self._using)
            .select_related("published_revision")
            .filter(published_revision__isnull=False, archived_at__isnull=True)
        )
        if type_key is not None:
            queryset = queryset.filter(type_key=str(type_key))
        total = queryset.count()
        records = queryset.order_by("-published_at", "-id")[offset : offset + limit]
        items = tuple(
            PublishedRevision(
                content_id=ContentId(record.id),
                type_key=ContentTypeKey(record.type_key),
                revision=revision_from_record(record.published_revision),
                published_at=record.published_at,
            )
            for record in records
            if record.published_at is not None and record.published_revision is not None
        )
        return items, total
