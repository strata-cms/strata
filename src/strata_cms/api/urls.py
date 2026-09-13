"""Versioned Strata API routes."""

from django.urls import include, path

from .health import HealthView

app_name = "api"
urlpatterns = [
    path("health/", HealthView.as_view(), name="health"),
    path("manage/", include("strata_cms.api.management.urls")),
    path("", include("strata_cms.api.delivery.urls")),
]
