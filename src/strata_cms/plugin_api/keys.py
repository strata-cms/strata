"""Stable plugin identifiers persisted or referenced across installations."""

import re
from dataclasses import dataclass

from strata_cms.plugin_api.errors import InvalidPluginKeyError

_PLUGIN_KEY = re.compile(r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+$")
_MAX_KEY_LENGTH = 200


@dataclass(frozen=True, slots=True, order=True)
class PluginKey:
    """Stable namespaced identifier such as ``acme_blog.core``."""

    value: str

    def __post_init__(self) -> None:
        """Validate the durable plugin identifier."""
        if len(self.value) > _MAX_KEY_LENGTH or not _PLUGIN_KEY.fullmatch(self.value):
            raise InvalidPluginKeyError(
                "Plugin keys must be <= 200 chars and use lowercase namespaced "
                "identifiers such as 'acme_blog.core'."
            )

    def __str__(self) -> str:
        """Return the stable string representation."""
        return self.value
