"""Read-only application service backing the public Delivery API."""

from dataclasses import dataclass
from datetime import datetime, timedelta

from strata_cms.application.ports.cache import Cache
from strata_cms.application.ports.content_delivery import ContentDeliveryQueries
from strata_cms.application.ports.content_types import ContentTypeService
from strata_cms.domain.value_objects import ContentId, ContentTypeKey, RevisionId

DEFAULT_DELIVERY_CACHE_TTL = timedelta(seconds=60)
"""Short TTL, disposable cache-aside: no active invalidation on publish/archive."""


@dataclass(frozen=True, slots=True)
class PublishedContent:
    """Delivery-ready published content for the public Delivery API."""

    content_id: ContentId
    type_key: ContentTypeKey
    revision_id: RevisionId
    revision_number: int
    published_at: datetime
    data: dict[str, object]


@dataclass(frozen=True, slots=True)
class PublishedContentPage:
    """One page of published content for the public Delivery API."""

    items: tuple[PublishedContent, ...]
    total_count: int
    limit: int
    offset: int


def get_published_content(
    content_id: ContentId,
    *,
    queries: ContentDeliveryQueries,
    content_types: ContentTypeService,
    cache: Cache | None = None,
    cache_ttl: timedelta = DEFAULT_DELIVERY_CACHE_TTL,
) -> PublishedContent | None:
    """Return the current public revision rendered for delivery, if published."""
    cache_key = f"strata:delivery:content:{content_id}"
    if cache is not None:
        cached = cache.get(cache_key)
        if isinstance(cached, PublishedContent):
            return cached

    published = queries.get_published(content_id)
    if published is None:
        return None
    data = content_types.delivery_data(published.revision)
    result = PublishedContent(
        content_id=published.content_id,
        type_key=published.type_key,
        revision_id=published.revision.id,
        revision_number=published.revision.number,
        published_at=published.published_at,
        data=data,
    )
    if cache is not None:
        cache.set(cache_key, result, ttl=cache_ttl)
    return result


def list_published_content(
    *,
    type_key: ContentTypeKey | None,
    limit: int,
    offset: int,
    queries: ContentDeliveryQueries,
    content_types: ContentTypeService,
    cache: Cache | None = None,
    cache_ttl: timedelta = DEFAULT_DELIVERY_CACHE_TTL,
) -> PublishedContentPage:
    """Return one page of published content, optionally filtered by type."""
    cache_key = f"strata:delivery:content-list:{type_key or '_all'}:{limit}:{offset}"
    if cache is not None:
        cached = cache.get(cache_key)
        if isinstance(cached, PublishedContentPage):
            return cached

    raw_items, total_count = queries.list_published(
        type_key=type_key,
        limit=limit,
        offset=offset,
    )
    items = tuple(
        PublishedContent(
            content_id=item.content_id,
            type_key=item.type_key,
            revision_id=item.revision.id,
            revision_number=item.revision.number,
            published_at=item.published_at,
            data=content_types.delivery_data(item.revision),
        )
        for item in raw_items
    )
    page = PublishedContentPage(
        items=items,
        total_count=total_count,
        limit=limit,
        offset=offset,
    )
    if cache is not None:
        cache.set(cache_key, page, ttl=cache_ttl)
    return page
