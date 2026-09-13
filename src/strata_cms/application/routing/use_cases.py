"""Content route write use cases: attach/move/detach nodes in the page tree.

Path rebuilds are synchronous and transactional: a move/rename recomputes the
projected path for the moved node and every descendant inside the same
transaction as the route change, per the documented requirement that
route/publication state transitions stay transactionally consistent.
"""

from strata_cms.application.errors import (
    RouteAlreadyAttachedError,
    RouteHasChildrenError,
    RouteNotFoundError,
    SlugConflictError,
)
from strata_cms.application.ports.authorization import (
    ContentAction,
    ContentActor,
    ContentAuthorizationPolicy,
)
from strata_cms.application.ports.route_uow import RouteUnitOfWork
from strata_cms.application.routing.commands import AttachRoute, DetachRoute, MoveRoute
from strata_cms.application.routing.results import RouteResult
from strata_cms.domain.errors import ConcurrentModificationError, RouteCycleError
from strata_cms.domain.route import ContentRoute
from strata_cms.domain.value_objects import ContentId


def attach_route(
    command: AttachRoute,
    *,
    uow: RouteUnitOfWork,
    policy: ContentAuthorizationPolicy,
    actor: ContentActor,
) -> RouteResult:
    """Attach a new route to content that has none yet."""
    policy.authorize(actor, ContentAction.CHANGE)
    with uow:
        if uow.routes.get(command.content_id) is not None:
            raise RouteAlreadyAttachedError(command.content_id)
        if command.parent_id is not None and uow.routes.get(command.parent_id) is None:
            raise RouteNotFoundError(command.parent_id)
        if uow.routes.get_by_parent_and_slug(command.parent_id, command.slug):
            raise SlugConflictError(parent_id=command.parent_id, slug=command.slug)

        route = ContentRoute(
            content_id=command.content_id,
            parent_id=command.parent_id,
            slug=command.slug,
        )
        uow.routes.add(route)
        path = _rebuild_subtree_paths(uow, route)
        uow.commit()

    return _to_result(route, path)


def move_route(
    command: MoveRoute,
    *,
    uow: RouteUnitOfWork,
    policy: ContentAuthorizationPolicy,
    actor: ContentActor,
) -> RouteResult:
    """Move and/or rename an existing route, rebuilding subtree paths."""
    policy.authorize(actor, ContentAction.CHANGE)
    with uow:
        route = uow.routes.get(command.content_id)
        if route is None:
            raise RouteNotFoundError(command.content_id)
        if route.version != command.expected_version:
            raise ConcurrentModificationError(
                f"Route for '{command.content_id}' changed since version "
                f"{command.expected_version}."
            )

        if command.parent_id is not None:
            if uow.routes.get(command.parent_id) is None:
                raise RouteNotFoundError(command.parent_id)
            if command.parent_id == command.content_id or _is_descendant(
                uow, command.content_id, command.parent_id
            ):
                raise RouteCycleError(
                    f"Cannot move '{command.content_id}' under itself or a "
                    "descendant of itself."
                )

        sibling = uow.routes.get_by_parent_and_slug(command.parent_id, command.slug)
        if sibling is not None and sibling.content_id != command.content_id:
            raise SlugConflictError(parent_id=command.parent_id, slug=command.slug)

        moved = route.moved_to(parent_id=command.parent_id, slug=command.slug)
        uow.routes.update(moved, expected_version=command.expected_version)
        path = _rebuild_subtree_paths(uow, moved)
        uow.commit()

    return _to_result(moved, path)


def detach_route(
    command: DetachRoute,
    *,
    uow: RouteUnitOfWork,
    policy: ContentAuthorizationPolicy,
    actor: ContentActor,
) -> None:
    """Remove a route that has no children."""
    policy.authorize(actor, ContentAction.CHANGE)
    with uow:
        route = uow.routes.get(command.content_id)
        if route is None:
            raise RouteNotFoundError(command.content_id)
        if route.version != command.expected_version:
            raise ConcurrentModificationError(
                f"Route for '{command.content_id}' changed since version "
                f"{command.expected_version}."
            )
        if uow.routes.list_children(command.content_id):
            raise RouteHasChildrenError(command.content_id)

        uow.routes.delete(command.content_id)
        uow.paths.remove(command.content_id)
        uow.commit()


def _is_descendant(
    uow: RouteUnitOfWork,
    ancestor_id: ContentId,
    candidate_id: ContentId,
) -> bool:
    """Return whether `candidate_id` is anywhere below `ancestor_id`."""
    pending = list(uow.routes.list_children(ancestor_id))
    while pending:
        node = pending.pop()
        if node.content_id == candidate_id:
            return True
        pending.extend(uow.routes.list_children(node.content_id))
    return False


def _compute_path(uow: RouteUnitOfWork, route: ContentRoute) -> str:
    """Walk the parent chain to compute one node's full projected path."""
    segments = [route.slug]
    parent_id = route.parent_id
    while parent_id is not None:
        parent = uow.routes.get(parent_id)
        if parent is None:
            raise RouteNotFoundError(parent_id)  # pragma: no cover - invariant guard
        segments.append(parent.slug)
        parent_id = parent.parent_id
    return "/".join(reversed(segments))


def _rebuild_subtree_paths(uow: RouteUnitOfWork, node: ContentRoute) -> str:
    """Recompute the projected path for `node` and every descendant."""
    root_path = _compute_path(uow, node)
    uow.paths.set_path(node.content_id, root_path)
    _rebuild_children_paths(uow, node.content_id, root_path)
    return root_path


def _rebuild_children_paths(
    uow: RouteUnitOfWork,
    parent_id: ContentId,
    parent_path: str,
) -> None:
    for child in uow.routes.list_children(parent_id):
        child_path = f"{parent_path}/{child.slug}"
        uow.paths.set_path(child.content_id, child_path)
        _rebuild_children_paths(uow, child.content_id, child_path)


def _to_result(route: ContentRoute, path: str) -> RouteResult:
    return RouteResult(
        content_id=route.content_id,
        parent_id=route.parent_id,
        slug=route.slug,
        version=route.version,
        path=path,
    )
