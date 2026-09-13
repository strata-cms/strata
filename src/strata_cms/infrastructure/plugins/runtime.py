"""Compile installed Django Strata plugins into one frozen runtime registry."""

from functools import lru_cache

from django.apps import apps
from django.core.exceptions import AppRegistryNotReady

from strata_cms import __version__
from strata_cms.plugin_api.django import StrataPluginConfig
from strata_cms.plugin_api.registry import StrataRegistry, StrataRegistryBuilder


@lru_cache(maxsize=1)
def get_strata_registry() -> StrataRegistry:
    """Build the immutable registry from installed ``StrataPluginConfig`` apps."""
    if not apps.ready:
        raise AppRegistryNotReady(
            "Strata registry cannot compile before Django app loading completes."
        )

    builder = StrataRegistryBuilder()
    plugin_configs = sorted(
        (
            config
            for config in apps.get_app_configs()
            if isinstance(config, StrataPluginConfig)
        ),
        key=lambda config: str(config.strata_plugin.key),
    )
    for config in plugin_configs:
        builder.register_plugin(config.strata_plugin)
    for config in plugin_configs:
        config.register_strata(builder.registrar_for(config.strata_plugin.key))
    return builder.build(strata_version=__version__)


def reset_strata_registry() -> None:
    """Clear the compiled registry cache for isolated tests/bootstrap tooling."""
    get_strata_registry.cache_clear()
