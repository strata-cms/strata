"""Errors raised by the public plugin and content-schema contracts."""

from collections.abc import Sequence

from strata_cms.domain.value_objects import ContentTypeKey
from strata_cms.plugin_api.schema import ValidationIssue


class PluginAPIError(Exception):
    """Base class for plugin API failures."""


class RegistryConfigurationError(PluginAPIError):
    """Base class for invalid plugin/registry configuration."""


class RegistryFrozenError(RegistryConfigurationError):
    """Raised when code attempts to mutate a consumed registry builder."""


class InvalidPluginKeyError(RegistryConfigurationError, ValueError):
    """Raised when a plugin key is not a stable namespaced identifier."""


class DuplicatePluginError(RegistryConfigurationError):
    """Raised when two plugins use the same stable key."""


class DuplicateContentTypeError(RegistryConfigurationError):
    """Raised when two content types use the same stable key."""


class DuplicateBlockTypeError(RegistryConfigurationError):
    """Raised when two blocks use the same stable key."""


class UnknownBlockReferenceError(RegistryConfigurationError):
    """Raised when a definition references an unregistered block type."""


class UnknownPluginOwnerError(RegistryConfigurationError):
    """Raised when a content type claims an unregistered owner plugin."""


class MissingPluginDependencyError(RegistryConfigurationError):
    """Raised when a required plugin is not installed."""


class UndeclaredPluginDependencyError(RegistryConfigurationError):
    """Raised when a plugin references definitions from an undeclared dependency."""


class IncompatiblePluginVersionError(RegistryConfigurationError):
    """Raised when an installed dependency does not satisfy a version range."""


class IncompatibleCMSVersionError(RegistryConfigurationError):
    """Raised when a plugin does not support the running CMS version."""


class UnsupportedPluginAPIVersionError(RegistryConfigurationError):
    """Raised when a plugin targets an unsupported public plugin API."""


class PluginDependencyCycleError(RegistryConfigurationError):
    """Raised when plugin dependencies contain a cycle."""


class ContentTypeNotFoundError(PluginAPIError, LookupError):
    """Raised when no installed plugin owns a persisted content type."""

    def __init__(self, key: ContentTypeKey) -> None:
        """Capture the unregistered content type key."""
        super().__init__(f"Content type '{key}' is not registered.")
        self.key = key


class SchemaError(PluginAPIError):
    """Base class for content-schema failures."""


class InvalidSchemaMigrationError(RegistryConfigurationError, SchemaError):
    """Raised for duplicate, non-sequential, or incomplete migration chains."""


class UnsupportedSchemaVersionError(SchemaError):
    """Raised when persisted data is newer than the installed schema."""


class SchemaDecodeError(SchemaError, ValueError):
    """Raised when JSON payload cannot be decoded into typed content."""


class BlockTypeNotFoundError(SchemaError, LookupError):
    """Raised when persisted content references an unavailable block type."""

    def __init__(self, key: object) -> None:
        """Capture the unregistered block type key."""
        super().__init__(f"Block type '{key}' is not registered.")
        self.key = key


class InvalidBlockEnvelopeError(SchemaError, ValueError):
    """Raised when persisted block JSON does not match the stable envelope."""


class BlockValidationError(SchemaError, ValueError):
    """Raised when a typed block or block tree violates declared constraints."""

    def __init__(self, issues: Sequence[ValidationIssue]) -> None:
        """Capture the block validation issues that caused this failure."""
        self.issues = tuple(issues)
        super().__init__("Block validation failed.")


class ContentValidationError(SchemaError, ValueError):
    """Raised when typed content violates content-type validation rules."""

    def __init__(self, issues: Sequence[ValidationIssue]) -> None:
        """Capture the content validation issues that caused this failure."""
        self.issues = tuple(issues)
        super().__init__("Content validation failed.")
