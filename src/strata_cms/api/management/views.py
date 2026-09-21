"""Management API endpoints shared conceptually with the Django Admin editor."""

from dataclasses import asdict
from uuid import UUID

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from strata_cms.api.errors import public_error_detail
from strata_cms.api.management.permissions import HasStrataManagementPermission
from strata_cms.api.management.serializers import (
    AttachRouteSerializer,
    ContentLifecycleSerializer,
    CreateContentSerializer,
    CreateRevisionSerializer,
    MoveRouteSerializer,
    PublishRevisionSerializer,
)
from strata_cms.application.content.commands import (
    ArchiveContent,
    CreateContent,
    CreateRevision,
    PublishContent,
    RestoreContent,
)
from strata_cms.application.content.results import (
    ContentLifecycleResult,
    ContentWriteResult,
)
from strata_cms.application.content.use_cases import (
    archive_content,
    create_content,
    create_revision,
    publish_content,
    restore_content,
)
from strata_cms.application.errors import (
    ContentNotFoundError,
    ContentTypeUnavailableError,
    InvalidContentDataError,
    NotAuthorizedError,
    RevisionNotFoundError,
    RouteAlreadyAttachedError,
    RouteHasChildrenError,
    RouteNotFoundError,
    SlugConflictError,
)
from strata_cms.application.ports.authorization import ContentAction
from strata_cms.application.routing.commands import AttachRoute, DetachRoute, MoveRoute
from strata_cms.application.routing.results import RouteResult
from strata_cms.application.routing.use_cases import (
    attach_route,
    detach_route,
    move_route,
)
from strata_cms.config.services import (
    get_clock,
    get_content_policy,
    get_content_queries,
    get_content_type_service,
    get_editor_catalog,
    get_id_generator,
    get_route_repository,
    new_content_uow,
    new_route_uow,
)
from strata_cms.domain.errors import (
    ConcurrentModificationError,
    ContentArchivedError,
    InvalidContentTypeKeyError,
    RevisionOwnershipError,
    RouteCycleError,
)
from strata_cms.domain.value_objects import ContentId, ContentTypeKey, RevisionId
from strata_cms.infrastructure.authorization.actor import build_content_actor


class ManagementAPIView(APIView):
    """Base view requiring an authenticated staff user; see permissions.py."""

    permission_classes = [HasStrataManagementPermission]
    throttle_scope = "strata-management"


class ContentTypeListView(ManagementAPIView):
    """List installed content types and whether they expose editor metadata."""

    @extend_schema(
        operation_id="v1_manage_content_types_list",
        responses=OpenApiTypes.OBJECT,
    )
    def get(self, request: Request) -> Response:
        """Return content types for a management UI type chooser."""
        denied = _authorize(request, ContentAction.VIEW)
        if denied is not None:
            return denied
        items = [asdict(item) for item in get_editor_catalog().list_content_types()]
        return Response({"results": items})


class ContentTypeDetailView(ManagementAPIView):
    """Return the complete editor contract for one content type."""

    @extend_schema(
        operation_id="v1_manage_content_types_retrieve",
        responses=OpenApiTypes.OBJECT,
    )
    def get(self, request: Request, type_key: str) -> Response:
        """Return fields, relevant block types, constraints, and templates."""
        denied = _authorize(request, ContentAction.VIEW)
        if denied is not None:
            return denied
        try:
            key = ContentTypeKey(type_key)
        except InvalidContentTypeKeyError as exc:
            return Response(
                {"detail": public_error_detail(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        editor = get_editor_catalog().get_content_type(key)
        if editor is None:
            return Response(
                {"detail": f"Content type '{key}' is not available."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(asdict(editor))


class ContentCollectionView(ManagementAPIView):
    """Create a new content identity and initial immutable revision."""

    @extend_schema(
        request=CreateContentSerializer,
        responses={201: OpenApiTypes.OBJECT},
    )
    def post(self, request: Request) -> Response:
        """Validate content through its registered schema and persist it."""
        serializer = CreateContentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        type_value = serializer.validated_data["type"]
        schema_version = serializer.validated_data["schema_version"]
        data = serializer.validated_data["data"]
        if not isinstance(type_value, str) or not isinstance(schema_version, int):
            raise AssertionError("Serializer returned unexpected scalar types.")
        if not isinstance(data, dict):
            raise AssertionError("Serializer returned non-object content data.")
        actor = build_content_actor(request.user)
        try:
            result = create_content(
                CreateContent(
                    type_key=ContentTypeKey(type_value),
                    schema_version=schema_version,
                    data=data,
                    actor_id=actor.id,
                ),
                uow=new_content_uow(),
                clock=get_clock(),
                ids=get_id_generator(),
                content_types=get_content_type_service(),
                policy=get_content_policy(),
                actor=actor,
            )
        except (
            InvalidContentTypeKeyError,
            ContentTypeUnavailableError,
            InvalidContentDataError,
            NotAuthorizedError,
        ) as exc:
            return _application_error(exc)
        return Response(_write_result(result), status=status.HTTP_201_CREATED)


class ContentDocumentView(ManagementAPIView):
    """Load the latest working revision for one editor session."""

    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request: Request, content_id: UUID) -> Response:
        """Return current revision data plus optimistic concurrency metadata."""
        denied = _authorize(request, ContentAction.VIEW)
        if denied is not None:
            return denied
        document = get_content_queries().get_latest(ContentId(content_id))
        if document is None:
            return Response(
                {"detail": "Content was not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        try:
            prepared = get_content_type_service().prepare_for_write(
                type_key=document.type_key,
                schema_version=document.schema_version,
                data=document.data.as_dict(),
            )
        except (ContentTypeUnavailableError, InvalidContentDataError) as exc:
            return _application_error(exc)
        return Response(
            {
                "content_id": str(document.content_id),
                "type": str(document.type_key),
                "content_version": document.content_version,
                "revision_id": str(document.revision_id),
                "revision_number": document.revision_number,
                "schema_version": prepared.schema_version,
                "data": prepared.data.as_dict(),
                "published_revision_id": (
                    str(document.published_revision_id)
                    if document.published_revision_id is not None
                    else None
                ),
                "is_archived": document.is_archived,
            }
        )


class ContentRevisionDetailView(ManagementAPIView):
    """Load one historical revision, normalized to its current schema."""

    @extend_schema(
        operation_id="v1_manage_content_revision_retrieve",
        responses=OpenApiTypes.OBJECT,
    )
    def get(self, request: Request, content_id: UUID, revision_id: UUID) -> Response:
        """Return one revision's data, e.g. to preview it before restoring."""
        denied = _authorize(request, ContentAction.VIEW)
        if denied is not None:
            return denied
        document = get_content_queries().get_revision(
            ContentId(content_id),
            RevisionId(revision_id),
        )
        if document is None:
            return Response(
                {"detail": "Revision was not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        try:
            prepared = get_content_type_service().prepare_for_write(
                type_key=document.type_key,
                schema_version=document.schema_version,
                data=document.data.as_dict(),
            )
        except (ContentTypeUnavailableError, InvalidContentDataError) as exc:
            return _application_error(exc)
        return Response(
            {
                "content_id": str(document.content_id),
                "type": str(document.type_key),
                "content_version": document.content_version,
                "revision_id": str(document.revision_id),
                "revision_number": document.revision_number,
                "schema_version": prepared.schema_version,
                "data": prepared.data.as_dict(),
                "published_revision_id": (
                    str(document.published_revision_id)
                    if document.published_revision_id is not None
                    else None
                ),
                "is_archived": document.is_archived,
            }
        )


class ContentRevisionCreateView(ManagementAPIView):
    """List revision history or append a new immutable draft revision."""

    @extend_schema(
        operation_id="v1_manage_content_revisions_list",
        responses=OpenApiTypes.OBJECT,
    )
    def get(self, request: Request, content_id: UUID) -> Response:
        """Return revision id/number/schema/author/published-flag summaries."""
        denied = _authorize(request, ContentAction.VIEW)
        if denied is not None:
            return denied
        summaries = get_content_queries().list_revisions(ContentId(content_id))
        if not summaries:
            return Response(
                {"detail": "Content was not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(
            {
                "results": [
                    {
                        "revision_id": str(summary.revision_id),
                        "number": summary.number,
                        "schema_version": summary.schema_version,
                        "created_at": summary.created_at.isoformat(),
                        "created_by": str(summary.created_by),
                        "is_published": summary.is_published,
                    }
                    for summary in summaries
                ]
            }
        )

    @extend_schema(
        request=CreateRevisionSerializer,
        responses={201: OpenApiTypes.OBJECT},
    )
    def post(self, request: Request, content_id: UUID) -> Response:
        """Persist the whole working document after schema/block validation."""
        serializer = CreateRevisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        expected_version = serializer.validated_data["expected_version"]
        schema_version = serializer.validated_data["schema_version"]
        data = serializer.validated_data["data"]
        if not isinstance(expected_version, int) or not isinstance(schema_version, int):
            raise AssertionError("Serializer returned unexpected version types.")
        if not isinstance(data, dict):
            raise AssertionError("Serializer returned non-object content data.")
        actor = build_content_actor(request.user)
        try:
            result = create_revision(
                CreateRevision(
                    content_id=ContentId(content_id),
                    expected_version=expected_version,
                    schema_version=schema_version,
                    data=data,
                    actor_id=actor.id,
                ),
                uow=new_content_uow(),
                clock=get_clock(),
                ids=get_id_generator(),
                content_types=get_content_type_service(),
                policy=get_content_policy(),
                actor=actor,
            )
        except (
            ContentNotFoundError,
            InvalidContentDataError,
            ConcurrentModificationError,
            ContentArchivedError,
            NotAuthorizedError,
        ) as exc:
            return _application_error(exc)
        return Response(_write_result(result), status=status.HTTP_201_CREATED)


class ContentPublishView(ManagementAPIView):
    """Publish one selected existing revision."""

    @extend_schema(
        request=PublishRevisionSerializer,
        responses=OpenApiTypes.OBJECT,
    )
    def post(self, request: Request, content_id: UUID) -> Response:
        """Move the published pointer and enqueue the outbox event atomically."""
        serializer = PublishRevisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        expected_version = serializer.validated_data["expected_version"]
        revision_id = serializer.validated_data["revision_id"]
        if not isinstance(expected_version, int) or not isinstance(revision_id, UUID):
            raise AssertionError("Serializer returned unexpected publish types.")
        actor = build_content_actor(request.user)
        try:
            result = publish_content(
                PublishContent(
                    content_id=ContentId(content_id),
                    revision_id=RevisionId(revision_id),
                    expected_version=expected_version,
                    actor_id=actor.id,
                ),
                uow=new_content_uow(),
                clock=get_clock(),
                ids=get_id_generator(),
                content_types=get_content_type_service(),
                policy=get_content_policy(),
                actor=actor,
            )
        except (
            ContentNotFoundError,
            RevisionNotFoundError,
            InvalidContentDataError,
            ConcurrentModificationError,
            RevisionOwnershipError,
            ContentArchivedError,
            NotAuthorizedError,
        ) as exc:
            return _application_error(exc)
        return Response(_write_result(result))


class ContentArchiveView(ManagementAPIView):
    """Archive one content item, blocking further edits/publishes."""

    @extend_schema(
        request=ContentLifecycleSerializer,
        responses=OpenApiTypes.OBJECT,
    )
    def post(self, request: Request, content_id: UUID) -> Response:
        """Mark content archived; idempotent when already archived."""
        serializer = ContentLifecycleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        expected_version = serializer.validated_data["expected_version"]
        if not isinstance(expected_version, int):
            raise AssertionError("Serializer returned unexpected version type.")
        actor = build_content_actor(request.user)
        try:
            result = archive_content(
                ArchiveContent(
                    content_id=ContentId(content_id),
                    expected_version=expected_version,
                    actor_id=actor.id,
                ),
                uow=new_content_uow(),
                clock=get_clock(),
                ids=get_id_generator(),
                policy=get_content_policy(),
                actor=actor,
            )
        except (
            ContentNotFoundError,
            ConcurrentModificationError,
            NotAuthorizedError,
        ) as exc:
            return _application_error(exc)
        return Response(_lifecycle_result(result))


class ContentRestoreView(ManagementAPIView):
    """Restore one archived content item to an editable/publishable state."""

    @extend_schema(
        request=ContentLifecycleSerializer,
        responses=OpenApiTypes.OBJECT,
    )
    def post(self, request: Request, content_id: UUID) -> Response:
        """Clear archival; idempotent when not archived."""
        serializer = ContentLifecycleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        expected_version = serializer.validated_data["expected_version"]
        if not isinstance(expected_version, int):
            raise AssertionError("Serializer returned unexpected version type.")
        actor = build_content_actor(request.user)
        try:
            result = restore_content(
                RestoreContent(
                    content_id=ContentId(content_id),
                    expected_version=expected_version,
                    actor_id=actor.id,
                ),
                uow=new_content_uow(),
                clock=get_clock(),
                ids=get_id_generator(),
                policy=get_content_policy(),
                actor=actor,
            )
        except (
            ContentNotFoundError,
            ConcurrentModificationError,
            NotAuthorizedError,
        ) as exc:
            return _application_error(exc)
        return Response(_lifecycle_result(result))


class ContentRouteView(ManagementAPIView):
    """Read, attach, move/rename, or detach one content item's route."""

    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request: Request, content_id: UUID) -> Response:
        """Return the current route position, or 404 when not attached."""
        denied = _authorize(request, ContentAction.VIEW)
        if denied is not None:
            return denied
        route = get_route_repository().get(ContentId(content_id))
        if route is None:
            return Response(
                {"detail": "Content has no route."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(
            {
                "content_id": str(route.content_id),
                "parent_id": str(route.parent_id) if route.parent_id else None,
                "slug": route.slug,
                "version": route.version,
            }
        )

    @extend_schema(
        request=AttachRouteSerializer,
        responses={201: OpenApiTypes.OBJECT},
    )
    def post(self, request: Request, content_id: UUID) -> Response:
        """Attach a new route to content that has none yet."""
        serializer = AttachRouteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        parent_id = serializer.validated_data["parent_id"]
        slug = serializer.validated_data["slug"]
        actor = build_content_actor(request.user)
        try:
            result = attach_route(
                AttachRoute(
                    content_id=ContentId(content_id),
                    parent_id=ContentId(parent_id) if parent_id else None,
                    slug=str(slug),
                ),
                uow=new_route_uow(),
                policy=get_content_policy(),
                actor=actor,
            )
        except (
            RouteAlreadyAttachedError,
            RouteNotFoundError,
            SlugConflictError,
            NotAuthorizedError,
        ) as exc:
            return _application_error(exc)
        return Response(_route_result(result), status=status.HTTP_201_CREATED)

    @extend_schema(
        request=MoveRouteSerializer,
        responses=OpenApiTypes.OBJECT,
    )
    def patch(self, request: Request, content_id: UUID) -> Response:
        """Move and/or rename an existing route."""
        serializer = MoveRouteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        parent_id = serializer.validated_data["parent_id"]
        slug = serializer.validated_data["slug"]
        expected_version = serializer.validated_data["expected_version"]
        actor = build_content_actor(request.user)
        try:
            result = move_route(
                MoveRoute(
                    content_id=ContentId(content_id),
                    parent_id=ContentId(parent_id) if parent_id else None,
                    slug=str(slug),
                    expected_version=expected_version,
                ),
                uow=new_route_uow(),
                policy=get_content_policy(),
                actor=actor,
            )
        except (
            RouteNotFoundError,
            SlugConflictError,
            RouteCycleError,
            ConcurrentModificationError,
            NotAuthorizedError,
        ) as exc:
            return _application_error(exc)
        return Response(_route_result(result))

    @extend_schema(
        request=ContentLifecycleSerializer,
        responses={204: None},
    )
    def delete(self, request: Request, content_id: UUID) -> Response:
        """Detach a route that has no children."""
        serializer = ContentLifecycleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        expected_version = serializer.validated_data["expected_version"]
        actor = build_content_actor(request.user)
        try:
            detach_route(
                DetachRoute(
                    content_id=ContentId(content_id),
                    expected_version=expected_version,
                ),
                uow=new_route_uow(),
                policy=get_content_policy(),
                actor=actor,
            )
        except (
            RouteNotFoundError,
            RouteHasChildrenError,
            ConcurrentModificationError,
            NotAuthorizedError,
        ) as exc:
            return _application_error(exc)
        return Response(status=status.HTTP_204_NO_CONTENT)


def _authorize(request: Request, action: ContentAction) -> Response | None:
    """Return a 403 response when the actor may not perform a read action."""
    actor = build_content_actor(request.user)
    try:
        get_content_policy().authorize(actor, action)
    except NotAuthorizedError as exc:
        return _application_error(exc)
    return None


def _write_result(result: ContentWriteResult) -> dict[str, object]:
    return {
        "content_id": str(result.content_id),
        "revision_id": str(result.revision_id),
        "content_version": result.content_version,
        "revision_number": result.revision_number,
    }


def _lifecycle_result(result: ContentLifecycleResult) -> dict[str, object]:
    return {
        "content_id": str(result.content_id),
        "content_version": result.content_version,
        "is_archived": result.is_archived,
    }


def _route_result(result: RouteResult) -> dict[str, object]:
    return {
        "content_id": str(result.content_id),
        "parent_id": str(result.parent_id) if result.parent_id else None,
        "slug": result.slug,
        "version": result.version,
        "path": result.path,
    }


def _application_error(error: Exception) -> Response:
    code: int
    if isinstance(
        error, (ContentNotFoundError, RevisionNotFoundError, RouteNotFoundError)
    ):
        code = status.HTTP_404_NOT_FOUND
    elif isinstance(
        error,
        (
            ConcurrentModificationError,
            ContentArchivedError,
            RouteAlreadyAttachedError,
            SlugConflictError,
            RouteHasChildrenError,
        ),
    ):
        code = status.HTTP_409_CONFLICT
    elif isinstance(error, NotAuthorizedError):
        code = status.HTTP_403_FORBIDDEN
    else:
        code = status.HTTP_400_BAD_REQUEST

    payload: dict[str, object] = {"detail": public_error_detail(error)}
    if isinstance(error, InvalidContentDataError):
        payload["problems"] = [asdict(problem) for problem in error.problems]
    return Response(payload, status=code)
