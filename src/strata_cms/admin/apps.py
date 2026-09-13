"""Django application configuration for the Strata Admin presentation."""

from django.apps import AppConfig


class StrataAdminConfig(AppConfig):
    """Enable Unfold/Django Admin presentation adapters."""

    name = "strata_cms.admin"
    label = "strata_admin"
    verbose_name = "Strata Admin"
