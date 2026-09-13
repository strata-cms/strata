from uuid import UUID

import pytest
from django.db import IntegrityError
from django.utils import timezone

from strata_cms.domain.errors import ConcurrentModificationError
from strata_cms.domain.route import ContentRoute
from strata_cms.domain.value_objects import ActorId, ContentId, ContentTypeKey
from strata_cms.infrastructure.persistence.django.models import ContentRecord
from strata_cms.infrastructure.persistence.django.routing import (
    DjangoContentRouteRepository,
    DjangoRoutePathProjection,
)

ACTOR = ActorId("user:1")


def _content(content_id: ContentId) -> ContentRecord:
    return ContentRecord.objects.create(
        id=content_id,
        type_key=str(ContentTypeKey("tests.article")),
        created_at=timezone.now(),
        created_by=str(ACTOR),
    )


@pytest.mark.django_db
def test_add_then_get_round_trips_a_route() -> None:
    content_id = ContentId(UUID(int=1))
    _content(content_id)
    repository = DjangoContentRouteRepository()

    repository.add(ContentRoute(content_id=content_id, parent_id=None, slug="about"))

    fetched = repository.get(content_id)
    assert fetched is not None
    assert fetched.slug == "about"
    assert fetched.parent_id is None
    assert fetched.version == 0


@pytest.mark.django_db
def test_list_children_returns_only_direct_children_in_slug_order() -> None:
    parent_id = ContentId(UUID(int=1))
    child_a = ContentId(UUID(int=2))
    child_b = ContentId(UUID(int=3))
    grandchild = ContentId(UUID(int=4))
    for content_id in (parent_id, child_a, child_b, grandchild):
        _content(content_id)
    repository = DjangoContentRouteRepository()
    repository.add(ContentRoute(content_id=parent_id, parent_id=None, slug="parent"))
    repository.add(ContentRoute(content_id=child_b, parent_id=parent_id, slug="zzz"))
    repository.add(ContentRoute(content_id=child_a, parent_id=parent_id, slug="aaa"))
    repository.add(
        ContentRoute(content_id=grandchild, parent_id=child_a, slug="grandchild")
    )

    children = repository.list_children(parent_id)

    assert [child.content_id for child in children] == [child_a, child_b]


@pytest.mark.django_db
def test_update_rejects_stale_expected_version() -> None:
    content_id = ContentId(UUID(int=1))
    _content(content_id)
    repository = DjangoContentRouteRepository()
    route = ContentRoute(content_id=content_id, parent_id=None, slug="about")
    repository.add(route)

    with pytest.raises(ConcurrentModificationError):
        repository.update(
            route.moved_to(parent_id=None, slug="us"), expected_version=99
        )


@pytest.mark.django_db
def test_database_rejects_duplicate_root_slug() -> None:
    first_id = ContentId(UUID(int=1))
    second_id = ContentId(UUID(int=2))
    _content(first_id)
    _content(second_id)
    repository = DjangoContentRouteRepository()
    repository.add(ContentRoute(content_id=first_id, parent_id=None, slug="about"))

    with pytest.raises(IntegrityError):
        repository.add(ContentRoute(content_id=second_id, parent_id=None, slug="about"))


@pytest.mark.django_db
def test_database_rejects_duplicate_sibling_slug() -> None:
    parent_id = ContentId(UUID(int=1))
    child_a = ContentId(UUID(int=2))
    child_b = ContentId(UUID(int=3))
    for content_id in (parent_id, child_a, child_b):
        _content(content_id)
    repository = DjangoContentRouteRepository()
    repository.add(ContentRoute(content_id=parent_id, parent_id=None, slug="parent"))
    repository.add(ContentRoute(content_id=child_a, parent_id=parent_id, slug="team"))

    with pytest.raises(IntegrityError):
        repository.add(
            ContentRoute(content_id=child_b, parent_id=parent_id, slug="team")
        )


@pytest.mark.django_db
def test_path_projection_set_resolve_and_remove() -> None:
    content_id = ContentId(UUID(int=1))
    _content(content_id)
    projection = DjangoRoutePathProjection()

    projection.set_path(content_id, "about/team")
    assert projection.resolve("about/team") == content_id

    projection.set_path(content_id, "about-us/team")
    assert projection.resolve("about/team") is None
    assert projection.resolve("about-us/team") == content_id

    projection.remove(content_id)
    assert projection.resolve("about-us/team") is None
