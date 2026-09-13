"""Read-side application port for editor content documents."""

from typing import Protocol

from strata_cms.application.content.queries import EditableContent, RevisionSummary
from strata_cms.domain.value_objects import ContentId, RevisionId


class ContentEditorQueries(Protocol):
    """Load immutable DTOs optimized for management/editor presentation."""

    def get_latest(self, content_id: ContentId) -> EditableContent | None:
        """Return the latest revision and aggregate metadata, if present."""
        ...  # pragma: no cover - protocol declaration

    def list_revisions(self, content_id: ContentId) -> tuple[RevisionSummary, ...]:
        """Return every immutable revision for one content item, newest first."""
        ...  # pragma: no cover - protocol declaration

    def get_revision(
        self,
        content_id: ContentId,
        revision_id: RevisionId,
    ) -> EditableContent | None:
        """Return one specific historical revision owned by this content item."""
        ...  # pragma: no cover - protocol declaration
