"""Commands for content mutation use cases."""

from collections.abc import Mapping
from dataclasses import dataclass

from strata_cms.domain.value_objects import (
    ActorId,
    ContentId,
    ContentTypeKey,
    RevisionId,
)


@dataclass(frozen=True, slots=True)
class CreateContent:
    """Create a content identity and its initial immutable revision."""

    type_key: ContentTypeKey
    schema_version: int
    data: Mapping[str, object]
    actor_id: ActorId


@dataclass(frozen=True, slots=True)
class CreateRevision:
    """Append a new draft revision using optimistic concurrency."""

    content_id: ContentId
    expected_version: int
    schema_version: int
    data: Mapping[str, object]
    actor_id: ActorId


@dataclass(frozen=True, slots=True)
class PublishContent:
    """Publish one existing revision using optimistic concurrency."""

    content_id: ContentId
    revision_id: RevisionId
    expected_version: int
    actor_id: ActorId


@dataclass(frozen=True, slots=True)
class ArchiveContent:
    """Archive one content item, blocking further edits/publishes."""

    content_id: ContentId
    expected_version: int
    actor_id: ActorId


@dataclass(frozen=True, slots=True)
class RestoreContent:
    """Restore one archived content item to an editable/publishable state."""

    content_id: ContentId
    expected_version: int
    actor_id: ActorId
