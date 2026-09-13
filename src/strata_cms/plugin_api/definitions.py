"""Immutable plugin and content-type definitions."""

from dataclasses import dataclass, field
from enum import StrEnum

from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import InvalidVersion, Version

from strata_cms.domain.revision import RevisionData
from strata_cms.domain.value_objects import ContentTypeKey
from strata_cms.plugin_api.blocks import BlockFieldDefinition, block_fields_are_unique
from strata_cms.plugin_api.editor import (
    BlockCollectionEditorField,
    ContentEditorDefinition,
    ScalarEditorField,
)
from strata_cms.plugin_api.errors import (
    ContentValidationError,
    RegistryConfigurationError,
    SchemaDecodeError,
)
from strata_cms.plugin_api.keys import PluginKey
from strata_cms.plugin_api.migrations import SchemaMigrationSet
from strata_cms.plugin_api.schema import ContentDeliverySerializer, ContentSchema


class ContentCapability(StrEnum):
    """Small set of cross-cutting capabilities understood by Strata core."""

    PUBLISHABLE = "publishable"
    PREVIEWABLE = "previewable"
    SEARCHABLE = "searchable"
    ROUTABLE = "routable"
    TRANSLATABLE = "translatable"


@dataclass(frozen=True, slots=True)
class PluginRequirement:
    """Dependency on another installed plugin and optional version range."""

    key: PluginKey
    version: str = ""

    def __post_init__(self) -> None:
        """Validate the PEP 440 dependency constraint once at registration."""
        try:
            SpecifierSet(self.version)
        except InvalidSpecifier as exc:
            raise RegistryConfigurationError(
                f"Invalid version requirement '{self.version}' for plugin '{self.key}'."
            ) from exc


@dataclass(frozen=True, slots=True)
class PluginDefinition:
    """Declarative metadata for one Strata plugin package."""

    key: PluginKey
    version: str
    requires_strata: str = ""
    requires_plugins: tuple[PluginRequirement, ...] = ()
    plugin_api_version: int = 1

    def __post_init__(self) -> None:
        """Validate static version metadata without performing I/O."""
        if self.plugin_api_version < 1:
            raise RegistryConfigurationError("Plugin API version must be positive.")
        try:
            Version(self.version)
            SpecifierSet(self.requires_strata)
        except (InvalidVersion, InvalidSpecifier) as exc:
            raise RegistryConfigurationError(
                f"Invalid version metadata for plugin '{self.key}'."
            ) from exc

        requirement_keys = [requirement.key for requirement in self.requires_plugins]
        if len(requirement_keys) != len(set(requirement_keys)):
            raise RegistryConfigurationError(
                f"Plugin '{self.key}' declares a dependency more than once."
            )


@dataclass(frozen=True, slots=True)
class EncodedContent:
    """Canonical current-version representation emitted by a content type."""

    schema_version: int
    data: RevisionData


@dataclass(frozen=True, slots=True)
class ContentTypeDefinition[T]:
    """Declarative, strongly typed definition of one revision content type."""

    key: ContentTypeKey
    schema_version: int
    schema: ContentSchema[T]
    migrations: SchemaMigrationSet = field(default_factory=SchemaMigrationSet)
    delivery: ContentDeliverySerializer[T] | None = None
    capabilities: frozenset[ContentCapability] = field(default_factory=frozenset)
    block_fields: tuple[BlockFieldDefinition, ...] = ()
    editor: ContentEditorDefinition | None = None

    def __post_init__(self) -> None:
        """Validate schema history and declared structured-block fields."""
        self.migrations.validate_for(self.schema_version)
        if not block_fields_are_unique(self.block_fields):
            raise RegistryConfigurationError(
                f"Content type '{self.key}' has duplicate block field paths."
            )
        if self.editor is not None:
            block_paths = {field.path for field in self.block_fields}
            editor_block_paths = {
                field.path
                for field in self.editor.fields
                if isinstance(field, BlockCollectionEditorField)
            }
            unknown = editor_block_paths - block_paths
            if unknown:
                rendered = ", ".join(".".join(path) for path in sorted(unknown))
                raise RegistryConfigurationError(
                    f"Content type '{self.key}' editor references non-block "
                    f"field(s): {rendered}."
                )
            scalar_block_paths = {
                field.path
                for field in self.editor.fields
                if isinstance(field, ScalarEditorField) and field.path in block_paths
            }
            if scalar_block_paths:
                rendered = ", ".join(
                    ".".join(path) for path in sorted(scalar_block_paths)
                )
                raise RegistryConfigurationError(
                    f"Content type '{self.key}' editor treats block field(s) as "
                    f"scalar: {rendered}."
                )

    def migrate_data(
        self,
        *,
        schema_version: int,
        data: RevisionData,
    ) -> RevisionData:
        """Upgrade historical content JSON to the current content schema."""
        return self.migrations.migrate(
            data,
            from_version=schema_version,
            to_version=self.schema_version,
        )

    def decode_current(self, data: RevisionData) -> T:
        """Decode and validate data already normalized to the current schema."""
        try:
            value = self.schema.deserialize(data)
        except SchemaDecodeError:
            raise
        except (TypeError, ValueError, KeyError) as exc:
            raise SchemaDecodeError(
                f"Could not decode content type '{self.key}'."
            ) from exc
        self._require_valid(value)
        return value

    def decode(self, *, schema_version: int, data: RevisionData) -> T:
        """Upgrade, decode, and validate one persisted revision snapshot."""
        return self.decode_current(
            self.migrate_data(schema_version=schema_version, data=data)
        )

    def decode_untyped(self, *, schema_version: int, data: RevisionData) -> object:
        """Type-erased runtime decoding used by heterogeneous registries."""
        return self.decode(schema_version=schema_version, data=data)

    def encode(self, value: T) -> EncodedContent:
        """Validate and encode typed current-version content."""
        self._require_valid(value)
        return EncodedContent(
            schema_version=self.schema_version,
            data=self.schema.serialize(value),
        )

    def encode_untyped(self, value: object) -> EncodedContent:
        """Encode a runtime value after checking its registered Python type."""
        if not isinstance(value, self.schema.value_type):
            raise SchemaDecodeError(
                f"Content type '{self.key}' expects "
                f"{self.schema.value_type.__name__}, got {type(value).__name__}."
            )
        return self.encode(value)

    def delivery_data(
        self,
        *,
        schema_version: int,
        data: RevisionData,
    ) -> dict[str, object]:
        """Decode historical data and produce current Delivery API JSON."""
        value = self.decode(schema_version=schema_version, data=data)
        if self.delivery is None:
            return self.schema.serialize(value).as_dict()
        return RevisionData.from_mapping(self.delivery.serialize(value)).as_dict()

    def _require_valid(self, value: T) -> None:
        issues = self.schema.validate(value)
        if issues:
            raise ContentValidationError(issues)
