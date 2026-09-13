import copy
from types import TracebackType
from uuid import UUID

import pytest

from strata_cms.application.errors import (
    NotAuthorizedError,
    RouteAlreadyAttachedError,
    RouteHasChildrenError,
    RouteNotFoundError,
    SlugConflictError,
)
from strata_cms.application.ports.authorization import ContentAction, ContentActor
from strata_cms.application.routing.commands import AttachRoute, DetachRoute, MoveRoute
from strata_cms.application.routing.use_cases import (
    attach_route,
    detach_route,
    move_route,
)
from strata_cms.domain.errors import ConcurrentModificationError, RouteCycleError
from strata_cms.domain.route import ContentRoute
from strata_cms.domain.value_objects import ActorId, ContentId

ACTOR_ID = ActorId("user:1")
ACTOR = ContentActor(id=ACTOR_ID, is_staff=True, permissions=frozenset())


class AllowAllPolicy:
    def authorize(self, actor: ContentActor, action: ContentAction) -> None:
        del actor, action


class DenyAllPolicy:
    def authorize(self, actor: ContentActor, action: ContentAction) -> None:
        del actor
        raise NotAuthorizedError(action.value)


POLICY = AllowAllPolicy()


class FakeRouteRepository:
    def __init__(self) -> None:
        self.items: dict[ContentId, ContentRoute] = {}

    def get(self, content_id: ContentId) -> ContentRoute | None:
        item = self.items.get(content_id)
        return copy.deepcopy(item) if item is not None else None

    def get_by_parent_and_slug(
        self, parent_id: ContentId | None, slug: str
    ) -> ContentRoute | None:
        for item in self.items.values():
            if item.parent_id == parent_id and item.slug == slug:
                return copy.deepcopy(item)
        return None

    def list_children(self, parent_id: ContentId | None) -> tuple[ContentRoute, ...]:
        return tuple(
            copy.deepcopy(item)
            for item in self.items.values()
            if item.parent_id == parent_id
        )

    def add(self, route: ContentRoute) -> None:
        self.items[route.content_id] = copy.deepcopy(route)

    def update(self, route: ContentRoute, *, expected_version: int) -> None:
        persisted = self.items.get(route.content_id)
        if persisted is None or persisted.version != expected_version:
            raise ConcurrentModificationError("stale fake route")
        self.items[route.content_id] = copy.deepcopy(route)

    def delete(self, content_id: ContentId) -> None:
        self.items.pop(content_id, None)


class FakeRoutePathProjection:
    def __init__(self) -> None:
        self.paths: dict[ContentId, str] = {}

    def set_path(self, content_id: ContentId, path: str) -> None:
        self.paths[content_id] = path

    def remove(self, content_id: ContentId) -> None:
        self.paths.pop(content_id, None)

    def resolve(self, path: str) -> ContentId | None:
        for content_id, stored in self.paths.items():
            if stored == path:
                return content_id
        return None


class FakeRouteUnitOfWork:
    def __init__(self) -> None:
        self.routes = FakeRouteRepository()
        self.paths = FakeRoutePathProjection()
        self.committed = False

    def __enter__(self) -> "FakeRouteUnitOfWork":
        self.committed = False
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        return None

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.committed = False


def _id(n: int) -> ContentId:
    return ContentId(UUID(int=n))


def test_attach_route_at_root_sets_path_to_slug() -> None:
    uow = FakeRouteUnitOfWork()

    result = attach_route(
        AttachRoute(content_id=_id(1), parent_id=None, slug="about"),
        uow=uow,
        policy=POLICY,
        actor=ACTOR,
    )

    assert result.path == "about"
    assert uow.committed is True


def test_attach_route_under_parent_builds_nested_path() -> None:
    uow = FakeRouteUnitOfWork()
    attach_route(
        AttachRoute(content_id=_id(1), parent_id=None, slug="about"),
        uow=uow,
        policy=POLICY,
        actor=ACTOR,
    )

    result = attach_route(
        AttachRoute(content_id=_id(2), parent_id=_id(1), slug="team"),
        uow=uow,
        policy=POLICY,
        actor=ACTOR,
    )

    assert result.path == "about/team"


def test_attach_route_rejects_content_that_already_has_one() -> None:
    uow = FakeRouteUnitOfWork()
    attach_route(
        AttachRoute(content_id=_id(1), parent_id=None, slug="about"),
        uow=uow,
        policy=POLICY,
        actor=ACTOR,
    )

    with pytest.raises(RouteAlreadyAttachedError):
        attach_route(
            AttachRoute(content_id=_id(1), parent_id=None, slug="other"),
            uow=uow,
            policy=POLICY,
            actor=ACTOR,
        )


def test_attach_route_rejects_duplicate_sibling_slug() -> None:
    uow = FakeRouteUnitOfWork()
    attach_route(
        AttachRoute(content_id=_id(1), parent_id=None, slug="about"),
        uow=uow,
        policy=POLICY,
        actor=ACTOR,
    )

    with pytest.raises(SlugConflictError):
        attach_route(
            AttachRoute(content_id=_id(2), parent_id=None, slug="about"),
            uow=uow,
            policy=POLICY,
            actor=ACTOR,
        )


def test_attach_route_rejects_unknown_parent() -> None:
    uow = FakeRouteUnitOfWork()

    with pytest.raises(RouteNotFoundError):
        attach_route(
            AttachRoute(content_id=_id(1), parent_id=_id(404), slug="about"),
            uow=uow,
            policy=POLICY,
            actor=ACTOR,
        )


def test_move_route_rebuilds_descendant_paths() -> None:
    uow = FakeRouteUnitOfWork()
    attach_route(
        AttachRoute(content_id=_id(1), parent_id=None, slug="about"),
        uow=uow,
        policy=POLICY,
        actor=ACTOR,
    )
    attach_route(
        AttachRoute(content_id=_id(2), parent_id=None, slug="company"),
        uow=uow,
        policy=POLICY,
        actor=ACTOR,
    )
    attach_route(
        AttachRoute(content_id=_id(3), parent_id=_id(1), slug="team"),
        uow=uow,
        policy=POLICY,
        actor=ACTOR,
    )

    result = move_route(
        MoveRoute(
            content_id=_id(1), parent_id=_id(2), slug="about", expected_version=0
        ),
        uow=uow,
        policy=POLICY,
        actor=ACTOR,
    )

    assert result.path == "company/about"
    assert uow.paths.paths[_id(3)] == "company/about/team"


def test_move_route_rejects_moving_under_own_descendant() -> None:
    uow = FakeRouteUnitOfWork()
    attach_route(
        AttachRoute(content_id=_id(1), parent_id=None, slug="about"),
        uow=uow,
        policy=POLICY,
        actor=ACTOR,
    )
    attach_route(
        AttachRoute(content_id=_id(2), parent_id=_id(1), slug="team"),
        uow=uow,
        policy=POLICY,
        actor=ACTOR,
    )

    with pytest.raises(RouteCycleError):
        move_route(
            MoveRoute(
                content_id=_id(1), parent_id=_id(2), slug="about", expected_version=0
            ),
            uow=uow,
            policy=POLICY,
            actor=ACTOR,
        )


def test_move_route_rejects_moving_under_itself() -> None:
    uow = FakeRouteUnitOfWork()
    attach_route(
        AttachRoute(content_id=_id(1), parent_id=None, slug="about"),
        uow=uow,
        policy=POLICY,
        actor=ACTOR,
    )

    with pytest.raises(RouteCycleError):
        move_route(
            MoveRoute(
                content_id=_id(1), parent_id=_id(1), slug="about", expected_version=0
            ),
            uow=uow,
            policy=POLICY,
            actor=ACTOR,
        )


def test_move_route_rejects_stale_version() -> None:
    uow = FakeRouteUnitOfWork()
    attach_route(
        AttachRoute(content_id=_id(1), parent_id=None, slug="about"),
        uow=uow,
        policy=POLICY,
        actor=ACTOR,
    )

    with pytest.raises(ConcurrentModificationError):
        move_route(
            MoveRoute(
                content_id=_id(1), parent_id=None, slug="us", expected_version=99
            ),
            uow=uow,
            policy=POLICY,
            actor=ACTOR,
        )


def test_detach_route_rejects_node_with_children() -> None:
    uow = FakeRouteUnitOfWork()
    attach_route(
        AttachRoute(content_id=_id(1), parent_id=None, slug="about"),
        uow=uow,
        policy=POLICY,
        actor=ACTOR,
    )
    attach_route(
        AttachRoute(content_id=_id(2), parent_id=_id(1), slug="team"),
        uow=uow,
        policy=POLICY,
        actor=ACTOR,
    )

    with pytest.raises(RouteHasChildrenError):
        detach_route(
            DetachRoute(content_id=_id(1), expected_version=0),
            uow=uow,
            policy=POLICY,
            actor=ACTOR,
        )


def test_detach_route_removes_leaf_node_and_its_path() -> None:
    uow = FakeRouteUnitOfWork()
    attach_route(
        AttachRoute(content_id=_id(1), parent_id=None, slug="about"),
        uow=uow,
        policy=POLICY,
        actor=ACTOR,
    )

    detach_route(
        DetachRoute(content_id=_id(1), expected_version=0),
        uow=uow,
        policy=POLICY,
        actor=ACTOR,
    )

    assert uow.routes.get(_id(1)) is None
    assert _id(1) not in uow.paths.paths


def test_attach_route_denied_by_policy() -> None:
    uow = FakeRouteUnitOfWork()

    with pytest.raises(NotAuthorizedError):
        attach_route(
            AttachRoute(content_id=_id(1), parent_id=None, slug="about"),
            uow=uow,
            policy=DenyAllPolicy(),
            actor=ACTOR,
        )
