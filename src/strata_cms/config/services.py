"""Django composition root for Strata presentation adapters."""

from functools import lru_cache

from strata_cms.application.content.search_indexing import reindex_from_event
from strata_cms.application.ports.authorization import ContentAuthorizationPolicy
from strata_cms.application.ports.cache import Cache
from strata_cms.application.ports.clock import Clock
from strata_cms.application.ports.content_delivery import ContentDeliveryQueries
from strata_cms.application.ports.content_queries import ContentEditorQueries
from strata_cms.application.ports.content_types import ContentTypeService
from strata_cms.application.ports.content_uow import ContentUnitOfWork
from strata_cms.application.ports.editors import EditorCatalog
from strata_cms.application.ports.ids import IdGenerator
from strata_cms.application.ports.messaging import DurableMessageQueue, MessageEnvelope
from strata_cms.application.ports.route_uow import RouteUnitOfWork
from strata_cms.application.ports.routing import (
    ContentRouteRepository,
    RoutePathProjection,
)
from strata_cms.application.ports.search import SearchBackend
from strata_cms.infrastructure.authorization.policy import StaffPermissionContentPolicy
from strata_cms.infrastructure.cache.django import DjangoCache
from strata_cms.infrastructure.clock.system import DjangoClock
from strata_cms.infrastructure.content_types.registry import RegistryContentTypeService
from strata_cms.infrastructure.editors.registry import RegistryEditorCatalog
from strata_cms.infrastructure.ids.uuid import Uuid4Generator
from strata_cms.infrastructure.persistence.django.outbox import DjangoOutboxQueue
from strata_cms.infrastructure.persistence.django.queries import (
    DjangoContentDeliveryQueries,
    DjangoContentEditorQueries,
)
from strata_cms.infrastructure.persistence.django.routing import (
    DjangoContentRouteRepository,
    DjangoRoutePathProjection,
    DjangoRouteUnitOfWork,
)
from strata_cms.infrastructure.persistence.django.search import PostgresSearchBackend
from strata_cms.infrastructure.persistence.django.unit_of_work import (
    DjangoContentUnitOfWork,
)
from strata_cms.infrastructure.plugins.runtime import get_strata_registry


@lru_cache(maxsize=1)
def get_content_type_service() -> ContentTypeService:
    """Return the registry-backed content schema service."""
    return RegistryContentTypeService(get_strata_registry())


@lru_cache(maxsize=1)
def get_editor_catalog() -> EditorCatalog:
    """Return management/editor metadata backed by the frozen registry."""
    return RegistryEditorCatalog(get_strata_registry())


def new_content_uow() -> ContentUnitOfWork:
    """Return a fresh transaction-scoped write Unit of Work."""
    return DjangoContentUnitOfWork()


def get_content_queries() -> ContentEditorQueries:
    """Return the optimized management content query adapter."""
    return DjangoContentEditorQueries()


def get_content_delivery_queries() -> ContentDeliveryQueries:
    """Return the optimized published-content query adapter."""
    return DjangoContentDeliveryQueries()


def get_clock() -> Clock:
    """Return the system clock adapter."""
    return DjangoClock()


def get_id_generator() -> IdGenerator:
    """Return the default random UUID generator."""
    return Uuid4Generator()


def get_outbox_queue(*, worker_id: str) -> DurableMessageQueue:
    """Return the PostgreSQL-backed durable queue over the transactional outbox."""
    return DjangoOutboxQueue(worker_id=worker_id)


@lru_cache(maxsize=1)
def get_content_policy() -> ContentAuthorizationPolicy:
    """Return the shared content authorization policy used by every caller."""
    return StaffPermissionContentPolicy()


@lru_cache(maxsize=1)
def get_cache() -> Cache:
    """Return the default Django-backed disposable cache adapter."""
    return DjangoCache()


@lru_cache(maxsize=1)
def get_search_backend() -> SearchBackend:
    """Return the baseline PostgreSQL-backed search adapter."""
    return PostgresSearchBackend()


def new_route_uow() -> RouteUnitOfWork:
    """Return a fresh transaction-scoped route write Unit of Work."""
    return DjangoRouteUnitOfWork()


def get_route_repository() -> ContentRouteRepository:
    """Return a read-only accessor over the content route tree."""
    return DjangoContentRouteRepository()


def get_route_path_projection() -> RoutePathProjection:
    """Return a read-only accessor over the route path projection."""
    return DjangoRoutePathProjection()


def dispatch_content_event(message: MessageEnvelope) -> None:
    """`strata_worker --dispatcher` entry point: keep the search index in sync.

    Opt-in: pass `--dispatcher strata_cms.config.services.dispatch_content_event`
    to `python manage.py strata_worker` to enable it.
    """
    reindex_from_event(
        message,
        queries=get_content_delivery_queries(),
        content_types=get_content_type_service(),
        search=get_search_backend(),
    )
