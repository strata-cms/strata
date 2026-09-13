"""Domain-facing repository contracts for content persistence."""

from typing import Protocol

from strata_cms.domain.content import Content
from strata_cms.domain.revision import Revision
from strata_cms.domain.value_objects import ContentId, RevisionId


class ContentRepository(Protocol):
    """Persist and rehydrate Content aggregate roots."""

    def get(self, content_id: ContentId) -> Content | None:
        """Return an aggregate by stable ID, or ``None`` when absent."""
        ...  # pragma: no cover - protocol declaration

    def add(self, content: Content) -> None:
        """Insert a new aggregate shell at version zero."""
        ...  # pragma: no cover - protocol declaration

    def update(self, content: Content, *, expected_version: int) -> None:
        """Persist aggregate state using optimistic compare-and-swap."""
        ...  # pragma: no cover - protocol declaration


class RevisionRepository(Protocol):
    """Persist and retrieve immutable revisions."""

    def get(self, revision_id: RevisionId) -> Revision | None:
        """Return an immutable revision by stable ID."""
        ...  # pragma: no cover - protocol declaration

    def add(self, revision: Revision) -> None:
        """Insert a new immutable revision."""
        ...  # pragma: no cover - protocol declaration
