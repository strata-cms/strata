"""Django application configuration for Strata plugin bootstrap/checks."""

from strata_cms import __version__
from strata_cms.plugin_api import PluginDefinition, PluginKey
from strata_cms.plugin_api.django import StrataPluginConfig

CORE_PLUGIN = PluginDefinition(
    key=PluginKey("strata.core"),
    version=__version__,
    requires_strata=">=0.1,<0.2",
)


class StrataCoreConfig(StrataPluginConfig):
    """Register Strata core itself and install registry system checks."""

    name = "strata_cms.infrastructure.plugins"
    label = "strata_core"
    verbose_name = "Strata Core"
    strata_plugin = CORE_PLUGIN

    def ready(self) -> None:
        """Register checks only; registry compilation remains centralized/lazy."""
        from strata_cms.infrastructure.plugins import checks  # noqa: F401
