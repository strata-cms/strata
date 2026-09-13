"""Application-owned port for installed content-type behavior."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol

from strata_cms.domain.revision import Revision, RevisionData
from strata_cms.domain.value_objects import ContentTypeKey


@dataclass(frozen=True, slots=True)
class PreparedContentData:
    """Validated current-version snapshot ready for immutable persistence."""

    schema_version: int
    data: RevisionData


class ContentTypeService(Protocol):
    """Validate and decode content without exposing registry implementation."""

    def prepare_for_write(
        self,
        *,
        type_key: ContentTypeKey,
        schema_version: int,
        data: Mapping[str, object],
    ) -> PreparedContentData:
        """Upgrade/validate input and return canonical current-version data."""
        ...  # pragma: no cover - protocol declaration

    def validate_revision(self, revision: Revision) -> None:
        """Require that one revision remains decodable by an installed type."""
        ...  # pragma: no cover - protocol declaration

    def delivery_data(self, revision: Revision) -> dict[str, object]:
        """Return current public JSON for one historical revision."""
        ...  # pragma: no cover - protocol declaration
