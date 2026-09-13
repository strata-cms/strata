"""Django application configuration for Strata persistence records."""

from django.apps import AppConfig


class StrataPersistenceConfig(AppConfig):
    """Own database records/migrations for the built-in CMS persistence adapter."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "strata_cms.infrastructure.persistence.django"
    label = "strata_persistence"
    verbose_name = "Strata"
