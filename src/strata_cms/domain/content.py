"""Content aggregate root."""

from dataclasses import dataclass, replace
from datetime import datetime
from typing import Self

from strata_cms.domain.errors import (
    ConcurrentModificationError,
    ContentArchivedError,
    InvalidRevisionError,
    RevisionOwnershipError,
)
from strata_cms.domain.revision import Revision, RevisionData
from strata_cms.domain.value_objects import (
    ActorId,
    ContentId,
    ContentTypeKey,
    RevisionId,
)


@dataclass(frozen=True, slots=True)
class Content:
    """Stable CMS content identity and revision/publication pointers."""

    id: ContentId
    type_key: ContentTypeKey
    created_at: datetime
    created_by: ActorId
    latest_revision_id: RevisionId | None = None
    latest_revision_number: int = 0
    published_revision_id: RevisionId | None = None
    published_at: datetime | None = None
    published_by: ActorId | None = None
    archived_at: datetime | None = None
    archived_by: ActorId | None = None
    version: int = 0

    def __post_init__(self) -> None:
        """Validate aggregate state loaded from any adapter."""
        if self.created_at.tzinfo is None or self.created_at.utcoffset() is None:
            raise InvalidRevisionError("Content timestamps must be timezone-aware.")
        if self.latest_revision_number < 0 or self.version < 0:
            raise InvalidRevisionError("Content counters cannot be negative.")
        if (self.latest_revision_id is None) != (self.latest_revision_number == 0):
            raise InvalidRevisionError(
                "Latest revision pointer and revision number must agree."
            )
        if self.version < self.latest_revision_number:
            raise InvalidRevisionError(
                "Aggregate version cannot trail the latest revision number."
            )
        if (self.published_revision_id is None) != (self.published_at is None):
            raise InvalidRevisionError("Published revision and timestamp must agree.")
        if (self.published_revision_id is None) != (self.published_by is None):
            raise InvalidRevisionError("Published revision and actor must agree.")
        if (self.archived_at is None) != (self.archived_by is None):
            raise InvalidRevisionError("Archived timestamp and actor must agree.")

    def require_version(self, expected_version: int) -> None:
        """Reject a command based on stale aggregate state."""
        if self.version != expected_version:
            raise ConcurrentModificationError(
                f"Content version is {self.version}, expected {expected_version}."
            )

    def require_not_archived(self) -> None:
        """Reject a mutation attempted against archived content."""
        if self.archived_at is not None:
            raise ContentArchivedError(
                f"Content '{self.id}' is archived and must be restored first."
            )

    def create_revision(
        self,
        *,
        revision_id: RevisionId,
        schema_version: int,
        data: RevisionData,
        actor_id: ActorId,
        now: datetime,
    ) -> tuple[Self, Revision]:
        """Return updated aggregate state plus the next immutable draft revision."""
        self.require_not_archived()
        revision = Revision(
            id=revision_id,
            content_id=self.id,
            number=self.latest_revision_number + 1,
            content_type=self.type_key,
            schema_version=schema_version,
            data=data,
            created_at=now,
            created_by=actor_id,
        )
        updated = replace(
            self,
            latest_revision_id=revision.id,
            latest_revision_number=revision.number,
            version=self.version + 1,
        )
        return updated, revision

    def publish(
        self,
        revision: Revision,
        *,
        actor_id: ActorId,
        now: datetime,
    ) -> tuple[Self, bool]:
        """Return state pointing public delivery at one owned revision."""
        self.require_not_archived()
        if revision.content_id != self.id:
            raise RevisionOwnershipError(
                "Cannot publish a revision owned by another content item."
            )
        if revision.content_type != self.type_key:
            raise RevisionOwnershipError(
                "Revision content type does not match its content item."
            )
        if self.published_revision_id == revision.id:
            return self, False

        updated = replace(
            self,
            published_revision_id=revision.id,
            published_at=now,
            published_by=actor_id,
            version=self.version + 1,
        )
        return updated, True

    def archive(self, *, actor_id: ActorId, now: datetime) -> tuple[Self, bool]:
        """Return state marking this content archived, idempotently."""
        if self.archived_at is not None:
            return self, False

        updated = replace(
            self,
            archived_at=now,
            archived_by=actor_id,
            version=self.version + 1,
        )
        return updated, True

    def restore(self) -> tuple[Self, bool]:
        """Return state clearing archival, idempotently. Publication is untouched."""
        if self.archived_at is None:
            return self, False

        updated = replace(
            self,
            archived_at=None,
            archived_by=None,
            version=self.version + 1,
        )
        return updated, True
