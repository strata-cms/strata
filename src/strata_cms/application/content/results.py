"""Stable result DTOs returned by content write use cases."""

from dataclasses import dataclass

from strata_cms.domain.value_objects import ContentId, RevisionId


@dataclass(frozen=True, slots=True)
class ContentWriteResult:
    """Identifiers/version resulting from a successful content mutation."""

    content_id: ContentId
    revision_id: RevisionId
    content_version: int
    revision_number: int


@dataclass(frozen=True, slots=True)
class ContentLifecycleResult:
    """Identity/version resulting from a revision-independent lifecycle change."""

    content_id: ContentId
    content_version: int
    is_archived: bool
