"""Django system checks for the compiled Strata plugin graph."""

from django.core.checks import Error, register

from strata_cms.infrastructure.plugins.runtime import get_strata_registry
from strata_cms.plugin_api.errors import RegistryConfigurationError


@register()
def check_strata_registry(**_kwargs: object) -> list[Error]:
    """Compile the registry so invalid plugin graphs fail checks and CI."""
    try:
        get_strata_registry()
    except RegistryConfigurationError as exc:
        return [
            Error(
                str(exc),
                hint="Fix plugin registration/dependencies before starting CMS.",
                id="strata.E001",
            )
        ]
    return []
