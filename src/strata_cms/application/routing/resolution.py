"""Resolve a published route path to delivery-ready content."""

from datetime import timedelta

from strata_cms.application.content.delivery import (
    DEFAULT_DELIVERY_CACHE_TTL,
    PublishedContent,
    get_published_content,
)
from strata_cms.application.ports.cache import Cache
from strata_cms.application.ports.content_delivery import ContentDeliveryQueries
from strata_cms.application.ports.content_types import ContentTypeService
from strata_cms.application.ports.routing import RoutePathProjection


def get_published_content_by_path(
    path: str,
    *,
    paths: RoutePathProjection,
    queries: ContentDeliveryQueries,
    content_types: ContentTypeService,
    cache: Cache | None = None,
    cache_ttl: timedelta = DEFAULT_DELIVERY_CACHE_TTL,
) -> PublishedContent | None:
    """Resolve a route path to its published content, if routed and published.

    Purely a structural lookup (path -> content_id) followed by the normal
    published-content read; an unpublished but routed item still resolves to
    `None` here, so routing can never leak drafts.
    """
    content_id = paths.resolve(path)
    if content_id is None:
        return None
    return get_published_content(
        content_id,
        queries=queries,
        content_types=content_types,
        cache=cache,
        cache_ttl=cache_ttl,
    )
