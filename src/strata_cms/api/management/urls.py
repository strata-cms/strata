"""Authenticated Management API routes."""

from django.urls import path

from strata_cms.api.management.views import (
    ContentArchiveView,
    ContentCollectionView,
    ContentDocumentView,
    ContentPublishView,
    ContentRestoreView,
    ContentRevisionCreateView,
    ContentRevisionDetailView,
    ContentRouteView,
    ContentTypeDetailView,
    ContentTypeListView,
)

app_name = "management"
urlpatterns = [
    path("content-types/", ContentTypeListView.as_view(), name="content-types"),
    path(
        "content-types/<str:type_key>/",
        ContentTypeDetailView.as_view(),
        name="content-type-detail",
    ),
    path("content/", ContentCollectionView.as_view(), name="content-create"),
    path(
        "content/<uuid:content_id>/",
        ContentDocumentView.as_view(),
        name="content-detail",
    ),
    path(
        "content/<uuid:content_id>/revisions/",
        ContentRevisionCreateView.as_view(),
        name="content-revision-create",
    ),
    path(
        "content/<uuid:content_id>/revisions/<uuid:revision_id>/",
        ContentRevisionDetailView.as_view(),
        name="content-revision-detail",
    ),
    path(
        "content/<uuid:content_id>/publish/",
        ContentPublishView.as_view(),
        name="content-publish",
    ),
    path(
        "content/<uuid:content_id>/archive/",
        ContentArchiveView.as_view(),
        name="content-archive",
    ),
    path(
        "content/<uuid:content_id>/restore/",
        ContentRestoreView.as_view(),
        name="content-restore",
    ),
    path(
        "content/<uuid:content_id>/route/",
        ContentRouteView.as_view(),
        name="content-route",
    ),
]
