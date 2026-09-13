"""Public Delivery API routes."""

from django.urls import path

from strata_cms.api.delivery.views import (
    ContentDeliveryListView,
    ContentDeliveryView,
    ContentSearchView,
    RouteResolutionView,
)

app_name = "delivery"
urlpatterns = [
    path(
        "content/",
        ContentDeliveryListView.as_view(),
        name="content-list",
    ),
    path(
        "content/<uuid:content_id>/",
        ContentDeliveryView.as_view(),
        name="content-detail",
    ),
    path(
        "search/",
        ContentSearchView.as_view(),
        name="content-search",
    ),
    path(
        "routes/<path:route_path>/",
        RouteResolutionView.as_view(),
        name="route-detail",
    ),
]
