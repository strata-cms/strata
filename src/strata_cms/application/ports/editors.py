"""Application port for discovering presentation-neutral editor contracts."""

from typing import Protocol

from strata_cms.application.editor_models import (
    ContentTypeEditorSpec,
    ContentTypeEditorSummary,
)
from strata_cms.domain.value_objects import ContentTypeKey


class EditorCatalog(Protocol):
    """Expose compiled editor metadata without leaking the plugin registry."""

    def list_content_types(self) -> tuple[ContentTypeEditorSummary, ...]:
        """Return installed content types in stable display order."""
        ...  # pragma: no cover - protocol declaration

    def get_content_type(self, key: ContentTypeKey) -> ContentTypeEditorSpec | None:
        """Return one complete editor contract, or ``None`` when unavailable."""
        ...  # pragma: no cover - protocol declaration
