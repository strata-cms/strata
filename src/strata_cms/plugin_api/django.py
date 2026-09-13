"""Optional Django integration contract for installed Strata plugin apps."""

from django.apps import AppConfig

from strata_cms.plugin_api.definitions import PluginDefinition
from strata_cms.plugin_api.registry import PluginRegistrar


class StrataPluginConfig(AppConfig):
    """Django AppConfig whose Strata registrations are compiled centrally."""

    strata_plugin: PluginDefinition

    def register_strata(self, registrar: PluginRegistrar) -> None:
        """Register owned definitions through a plugin-scoped registrar."""
        del registrar
