"""Public Delivery API views exposing only explicitly published content."""

from uuid import UUID

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from strata_cms.api.delivery.serializers import (
    ContentListQuerySerializer,
    ContentSearchQuerySerializer,
)
from strata_cms.api.errors import public_error_detail
from strata_cms.application.content.delivery import (
    PublishedContent,
    get_published_content,
    list_published_content,
)
from strata_cms.application.ports.search import SearchQuery
from strata_cms.application.routing.resolution import get_published_content_by_path
from strata_cms.config.services import (
    get_cache,
    get_content_delivery_queries,
    get_content_type_service,
    get_route_path_projection,
    get_search_backend,
)
from strata_cms.domain.errors import InvalidContentTypeKeyError
from strata_cms.domain.value_objects import ContentId, ContentTypeKey


class DeliveryAPIView(APIView):
    """Base view for the public, anonymous, rate-limited Delivery API."""

    permission_classes = [AllowAny]
    throttle_scope = "strata-delivery"


class ContentDeliveryView(DeliveryAPIView):
    """Return the current published revision for one content item."""

    @extend_schema(
        operation_id="v1_content_retrieve",
        responses=OpenApiTypes.OBJECT,
    )
    def get(self, request: Request, content_id: UUID) -> Response:
        """Render the published revision, or 404 when absent/unpublished."""
        del request
        published = get_published_content(
            ContentId(content_id),
            queries=get_content_delivery_queries(),
            content_types=get_content_type_service(),
            cache=get_cache(),
        )
        if published is None:
            return Response(
                {"detail": "Content was not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(_render(published))


class ContentDeliveryListView(DeliveryAPIView):
    """List published content, optionally filtered by content type."""

    @extend_schema(
        operation_id="v1_content_list",
        parameters=[
            OpenApiParameter("type", OpenApiTypes.STR, required=False),
            OpenApiParameter("limit", OpenApiTypes.INT, required=False),
            OpenApiParameter("offset", OpenApiTypes.INT, required=False),
        ],
        responses=OpenApiTypes.OBJECT,
    )
    def get(self, request: Request) -> Response:
        """Return one page of published content, newest-published first."""
        query = ContentListQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        type_value = query.validated_data.get("type")
        limit = query.validated_data["limit"]
        offset = query.validated_data["offset"]
        if not isinstance(limit, int) or not isinstance(offset, int):
            raise AssertionError("Serializer returned unexpected pagination types.")

        type_key: ContentTypeKey | None = None
        if type_value:
            try:
                type_key = ContentTypeKey(str(type_value))
            except InvalidContentTypeKeyError as exc:
                return Response(
                    {"detail": public_error_detail(exc)},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        page = list_published_content(
            type_key=type_key,
            limit=limit,
            offset=offset,
            queries=get_content_delivery_queries(),
            content_types=get_content_type_service(),
            cache=get_cache(),
        )
        return Response(
            {
                "count": page.total_count,
                "limit": page.limit,
                "offset": page.offset,
                "results": [_render(item) for item in page.items],
            }
        )


class RouteResolutionView(DeliveryAPIView):
    """Resolve one page-tree path to its published content."""

    @extend_schema(
        operation_id="v1_routes_retrieve",
        responses=OpenApiTypes.OBJECT,
    )
    def get(self, request: Request, route_path: str) -> Response:
        """Render the content routed at this exact path, or 404."""
        del request
        published = get_published_content_by_path(
            route_path,
            paths=get_route_path_projection(),
            queries=get_content_delivery_queries(),
            content_types=get_content_type_service(),
            cache=get_cache(),
        )
        if published is None:
            return Response(
                {"detail": "No published content at this path."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response({"path": route_path, **_render(published)})


class ContentSearchView(DeliveryAPIView):
    """Search published content via the baseline search backend."""

    @extend_schema(
        operation_id="v1_content_search",
        parameters=[
            OpenApiParameter("q", OpenApiTypes.STR, required=True),
            OpenApiParameter("type", OpenApiTypes.STR, required=False),
            OpenApiParameter("limit", OpenApiTypes.INT, required=False),
            OpenApiParameter("offset", OpenApiTypes.INT, required=False),
        ],
        responses=OpenApiTypes.OBJECT,
    )
    def get(self, request: Request) -> Response:
        """Return one page of search hits, most relevant first."""
        query = ContentSearchQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        text = query.validated_data["q"]
        type_value = query.validated_data.get("type")
        limit = query.validated_data["limit"]
        offset = query.validated_data["offset"]
        if (
            not isinstance(text, str)
            or not isinstance(limit, int)
            or not isinstance(offset, int)
        ):
            raise AssertionError("Serializer returned unexpected search types.")

        filters: dict[str, object] = {}
        if type_value:
            try:
                filters["type"] = str(ContentTypeKey(str(type_value)))
            except InvalidContentTypeKeyError as exc:
                return Response(
                    {"detail": public_error_detail(exc)},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        result = get_search_backend().search(
            SearchQuery(text=text, limit=limit, offset=offset, filters=filters)
        )
        return Response(
            {
                "count": result.total,
                "limit": limit,
                "offset": offset,
                "results": [
                    {
                        "content_id": str(hit.document_id),
                        "score": hit.score,
                        "fields": hit.fields,
                    }
                    for hit in result.hits
                ],
            }
        )


def _render(content: PublishedContent) -> dict[str, object]:
    return {
        "content_id": str(content.content_id),
        "type": str(content.type_key),
        "revision_id": str(content.revision_id),
        "revision_number": content.revision_number,
        "published_at": content.published_at.isoformat(),
        "data": content.data,
    }
