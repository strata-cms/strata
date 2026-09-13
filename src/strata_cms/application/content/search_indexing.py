"""Keep the search index in sync with content publish/archive/restore events.

Deliberately decoupled from the write use cases (same precedent as Delivery
caching): this is driven by the outbox worker's dispatcher, not called
synchronously from `publish_content`/`archive_content`/`restore_content`.
"""

from uuid import UUID

from strata_cms.application.content.delivery import get_published_content
from strata_cms.application.ports.content_delivery import ContentDeliveryQueries
from strata_cms.application.ports.content_types import ContentTypeService
from strata_cms.application.ports.messaging import MessageEnvelope
from strata_cms.application.ports.search import SearchBackend, SearchDocument
from strata_cms.domain.value_objects import ContentId

_PUBLISHED = "strata.content.published"
_ARCHIVED = "strata.content.archived"
_RESTORED = "strata.content.restored"
_RELEVANT_EVENT_TYPES = frozenset({_PUBLISHED, _ARCHIVED, _RESTORED})


def reindex_from_event(
    message: MessageEnvelope,
    *,
    queries: ContentDeliveryQueries,
    content_types: ContentTypeService,
    search: SearchBackend,
) -> None:
    """Index, re-index, or remove one content item in response to its event."""
    if message.type not in _RELEVANT_EVENT_TYPES:
        return
    content_id_raw = message.payload.get("content_id")
    if not isinstance(content_id_raw, str):
        return
    content_id = ContentId(UUID(content_id_raw))

    if message.type == _ARCHIVED:
        search.remove(content_id)
        return

    published = get_published_content(
        content_id,
        queries=queries,
        content_types=content_types,
    )
    if published is None:
        search.remove(content_id)
        return
    search.index(
        SearchDocument(
            id=content_id,
            text=_extract_text(published.data),
            fields={
                "type": str(published.type_key),
                "published_at": published.published_at.isoformat(),
            },
        )
    )


def _extract_text(value: object) -> str:
    """Flatten every string leaf of a JSON-like structure into indexable text."""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return " ".join(_extract_text(item) for item in value.values())
    if isinstance(value, list):
        return " ".join(_extract_text(item) for item in value)
    return ""
