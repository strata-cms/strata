from django.core.checks import run_checks

from strata_cms.infrastructure.plugins.apps import CORE_PLUGIN
from strata_cms.infrastructure.plugins.runtime import (
    get_strata_registry,
    reset_strata_registry,
)


def test_default_django_registry_contains_core_plugin() -> None:
    reset_strata_registry()

    registry = get_strata_registry()

    assert registry.plugins.get(CORE_PLUGIN.key) == CORE_PLUGIN


def test_default_registry_system_check_passes() -> None:
    reset_strata_registry()

    errors = [error for error in run_checks() if error.id == "strata.E001"]

    assert errors == []
