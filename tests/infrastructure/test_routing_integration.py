from uuid import UUID

import pytest
from django.utils import timezone

from strata_cms.application.ports.authorization import ContentAction, ContentActor
from strata_cms.application.routing.commands import AttachRoute, DetachRoute, MoveRoute
from strata_cms.application.routing.resolution import get_published_content_by_path
from strata_cms.application.routing.use_cases import (
    attach_route,
    detach_route,
    move_route,
)
from strata_cms.config.services import (
    get_content_delivery_queries,
    get_content_type_service,
    get_route_path_projection,
)
from strata_cms.domain.value_objects import ActorId, ContentId, ContentTypeKey
from strata_cms.infrastructure.persistence.django.models import ContentRecord
from strata_cms.infrastructure.persistence.django.routing import (
    DjangoRoutePathProjection,
    DjangoRouteUnitOfWork,
)

pytestmark = pytest.mark.django_db

ACTOR_ID = ActorId("user:1")
ACTOR = ContentActor(id=ACTOR_ID, is_staff=True, permissions=frozenset())


class AllowAllPolicy:
    def authorize(self, actor: ContentActor, action: ContentAction) -> None:
        del actor, action


POLICY = AllowAllPolicy()


def _content(n: int) -> ContentId:
    content_id = ContentId(UUID(int=n))
    ContentRecord.objects.create(
        id=content_id,
        type_key=str(ContentTypeKey("tests.article")),
        created_at=timezone.now(),
        created_by=str(ACTOR_ID),
    )
    return content_id


def test_attach_move_and_detach_against_the_real_database() -> None:
    about_id = _content(1)
    company_id = _content(2)
    team_id = _content(3)

    attach_route(
        AttachRoute(content_id=about_id, parent_id=None, slug="about"),
        uow=DjangoRouteUnitOfWork(),
        policy=POLICY,
        actor=ACTOR,
    )
    attach_route(
        AttachRoute(content_id=company_id, parent_id=None, slug="company"),
        uow=DjangoRouteUnitOfWork(),
        policy=POLICY,
        actor=ACTOR,
    )
    attach_route(
        AttachRoute(content_id=team_id, parent_id=about_id, slug="team"),
        uow=DjangoRouteUnitOfWork(),
        policy=POLICY,
        actor=ACTOR,
    )

    moved = move_route(
        MoveRoute(
            content_id=about_id,
            parent_id=company_id,
            slug="about",
            expected_version=0,
        ),
        uow=DjangoRouteUnitOfWork(),
        policy=POLICY,
        actor=ACTOR,
    )
    assert moved.path == "company/about"

    projection = DjangoRoutePathProjection()
    assert projection.resolve("company/about") == about_id
    assert projection.resolve("company/about/team") == team_id
    assert projection.resolve("about") is None
    assert projection.resolve("about/team") is None

    detach_route(
        DetachRoute(content_id=team_id, expected_version=0),
        uow=DjangoRouteUnitOfWork(),
        policy=POLICY,
        actor=ACTOR,
    )
    assert projection.resolve("company/about/team") is None


def test_get_published_content_by_path_returns_none_when_unpublished() -> None:
    about_id = _content(1)
    attach_route(
        AttachRoute(content_id=about_id, parent_id=None, slug="about"),
        uow=DjangoRouteUnitOfWork(),
        policy=POLICY,
        actor=ACTOR,
    )

    published = get_published_content_by_path(
        "about",
        paths=get_route_path_projection(),
        queries=get_content_delivery_queries(),
        content_types=get_content_type_service(),
    )

    assert published is None
