"""Deterministic builder and immutable runtime Strata registry."""

from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Protocol

from packaging.specifiers import SpecifierSet
from packaging.version import Version

from strata_cms.domain.revision import RevisionData
from strata_cms.domain.value_objects import ContentTypeKey
from strata_cms.plugin_api.blocks import (
    BlockCollection,
    BlockFieldDefinition,
    BlockListConstraint,
    BlockNode,
    BlockSlotDefinition,
    BlockTypeKey,
    EncodedBlockData,
    validate_collection_constraint,
)
from strata_cms.plugin_api.definitions import (
    ContentCapability,
    EncodedContent,
    PluginDefinition,
)
from strata_cms.plugin_api.editor import BlockEditorDefinition, ContentEditorDefinition
from strata_cms.plugin_api.errors import (
    BlockTypeNotFoundError,
    BlockValidationError,
    ContentTypeNotFoundError,
    DuplicateBlockTypeError,
    DuplicateContentTypeError,
    DuplicatePluginError,
    IncompatibleCMSVersionError,
    IncompatiblePluginVersionError,
    MissingPluginDependencyError,
    PluginDependencyCycleError,
    RegistryFrozenError,
    SchemaDecodeError,
    UndeclaredPluginDependencyError,
    UnknownBlockReferenceError,
    UnknownPluginOwnerError,
    UnsupportedPluginAPIVersionError,
)
from strata_cms.plugin_api.keys import PluginKey
from strata_cms.plugin_api.schema import ValidationIssue

STRATA_PLUGIN_API_VERSION = 1
_MISSING = object()


class RegisteredContentType(Protocol):
    """Type-erased runtime view of heterogeneous content definitions."""

    @property
    def key(self) -> ContentTypeKey:
        """Return the stable persisted content type key."""
        ...  # pragma: no cover - protocol declaration

    @property
    def schema_version(self) -> int:
        """Return the current persisted schema version."""
        ...  # pragma: no cover - protocol declaration

    @property
    def capabilities(self) -> frozenset[ContentCapability]:
        """Return cross-cutting capabilities understood by Strata core."""
        ...  # pragma: no cover - protocol declaration

    @property
    def block_fields(self) -> tuple[BlockFieldDefinition, ...]:
        """Return generic structured-block fields in the content payload."""
        ...  # pragma: no cover - protocol declaration

    @property
    def editor(self) -> ContentEditorDefinition | None:
        """Return optional presentation-neutral editing metadata."""
        ...  # pragma: no cover - protocol declaration

    def migrate_data(
        self,
        *,
        schema_version: int,
        data: RevisionData,
    ) -> RevisionData:
        """Upgrade historical content JSON to the current schema."""
        ...  # pragma: no cover - protocol declaration

    def decode_untyped(self, *, schema_version: int, data: RevisionData) -> object:
        """Decode and validate one historical snapshot."""
        ...  # pragma: no cover - protocol declaration

    def encode_untyped(self, value: object) -> EncodedContent:
        """Encode a runtime value using the registered schema."""
        ...  # pragma: no cover - protocol declaration

    def delivery_data(
        self,
        *,
        schema_version: int,
        data: RevisionData,
    ) -> dict[str, object]:
        """Return current public delivery JSON."""
        ...  # pragma: no cover - protocol declaration


class RegisteredBlockType(Protocol):
    """Type-erased runtime view of heterogeneous block definitions."""

    @property
    def key(self) -> BlockTypeKey:
        """Return the stable persisted block type key."""
        ...  # pragma: no cover - protocol declaration

    @property
    def schema_version(self) -> int:
        """Return the current persisted block schema version."""
        ...  # pragma: no cover - protocol declaration

    @property
    def slots(self) -> tuple[BlockSlotDefinition, ...]:
        """Return named nested block slots declared by this type."""
        ...  # pragma: no cover - protocol declaration

    @property
    def editor(self) -> BlockEditorDefinition | None:
        """Return optional presentation-neutral editing metadata."""
        ...  # pragma: no cover - protocol declaration

    def decode_untyped(self, *, schema_version: int, data: RevisionData) -> object:
        """Decode and validate one historical block payload."""
        ...  # pragma: no cover - protocol declaration

    def encode_untyped(self, value: object) -> EncodedBlockData:
        """Encode a runtime block value using the registered schema."""
        ...  # pragma: no cover - protocol declaration

    def delivery_data(
        self,
        *,
        schema_version: int,
        data: RevisionData,
    ) -> dict[str, object]:
        """Return public data for one historical block payload."""
        ...  # pragma: no cover - protocol declaration


class PluginRegistrar(Protocol):
    """Scoped registration surface given to one plugin during compilation."""

    def register_content_type(self, definition: RegisteredContentType) -> None:
        """Register a content type owned by the current plugin."""
        ...  # pragma: no cover - protocol declaration

    def register_block_type(self, definition: RegisteredBlockType) -> None:
        """Register a block type owned by the current plugin."""
        ...  # pragma: no cover - protocol declaration


class _ScopedPluginRegistrar:
    """Prevent plugin callbacks from claiming another plugin's ownership."""

    def __init__(self, builder: "StrataRegistryBuilder", owner: PluginKey) -> None:
        self._builder = builder
        self._owner = owner

    def register_content_type(self, definition: RegisteredContentType) -> None:
        """Register one content definition under the fixed owner."""
        self._builder._register_content_type(definition, owner=self._owner)

    def register_block_type(self, definition: RegisteredBlockType) -> None:
        """Register one block definition under the fixed owner."""
        self._builder._register_block_type(definition, owner=self._owner)


@dataclass(frozen=True, slots=True)
class RegisteredContentTypeEntry:
    """Runtime content definition plus the plugin that owns its stable key."""

    owner: PluginKey
    definition: RegisteredContentType


@dataclass(frozen=True, slots=True)
class RegisteredBlockTypeEntry:
    """Runtime block definition plus the plugin that owns its stable key."""

    owner: PluginKey
    definition: RegisteredBlockType


class PluginRegistry:
    """Immutable, dependency-ordered plugin metadata registry."""

    def __init__(self, plugins: Iterable[PluginDefinition]) -> None:
        """Freeze the dependency-ordered plugin sequence into a lookup."""
        ordered = tuple(plugins)
        self._ordered = ordered
        self._by_key: Mapping[PluginKey, PluginDefinition] = MappingProxyType(
            {plugin.key: plugin for plugin in ordered}
        )

    def get(self, key: PluginKey) -> PluginDefinition | None:
        """Return a plugin definition, or ``None`` when absent."""
        return self._by_key.get(key)

    def all(self) -> tuple[PluginDefinition, ...]:
        """Return plugins in deterministic dependency-first order."""
        return self._ordered


class ContentTypeRegistry:
    """Immutable runtime content-type lookup."""

    def __init__(self, entries: Iterable[RegisteredContentTypeEntry]) -> None:
        """Freeze registered content-type entries into a key-ordered lookup."""
        ordered = tuple(sorted(entries, key=lambda item: str(item.definition.key)))
        self._ordered = ordered
        self._by_key: Mapping[ContentTypeKey, RegisteredContentTypeEntry] = (
            MappingProxyType({entry.definition.key: entry for entry in ordered})
        )

    def get(self, key: ContentTypeKey) -> RegisteredContentTypeEntry | None:
        """Return a registered type and owner, or ``None`` when unavailable."""
        return self._by_key.get(key)

    def require(self, key: ContentTypeKey) -> RegisteredContentTypeEntry:
        """Return a registered type or fail with a stable CMS error."""
        entry = self.get(key)
        if entry is None:
            raise ContentTypeNotFoundError(key)
        return entry

    def all(self) -> tuple[RegisteredContentTypeEntry, ...]:
        """Return all content types in stable key order."""
        return self._ordered


class BlockTypeRegistry:
    """Immutable block lookup plus generic tree normalization/delivery."""

    def __init__(self, entries: Iterable[RegisteredBlockTypeEntry]) -> None:
        """Freeze registered block-type entries into a key-ordered lookup."""
        ordered = tuple(sorted(entries, key=lambda item: str(item.definition.key)))
        self._ordered = ordered
        self._by_key: Mapping[BlockTypeKey, RegisteredBlockTypeEntry] = (
            MappingProxyType({entry.definition.key: entry for entry in ordered})
        )

    def get(self, key: BlockTypeKey) -> RegisteredBlockTypeEntry | None:
        """Return one registered block type, or ``None`` when unavailable."""
        return self._by_key.get(key)

    def require(self, key: BlockTypeKey) -> RegisteredBlockTypeEntry:
        """Return one block definition or fail with a stable CMS error."""
        entry = self.get(key)
        if entry is None:
            raise BlockTypeNotFoundError(key)
        return entry

    def all(self) -> tuple[RegisteredBlockTypeEntry, ...]:
        """Return all block definitions in stable key order."""
        return self._ordered

    def normalize_collection(
        self,
        collection: BlockCollection,
        *,
        constraint: BlockListConstraint | None = None,
        path: str = "$",
    ) -> BlockCollection:
        """Migrate, decode, validate, and canonicalize one entire block tree."""
        effective = constraint or BlockListConstraint()
        validate_collection_constraint(collection, effective, path=path)
        normalized = tuple(
            self._normalize_node(block, path=f"{path}[{index}]")
            for index, block in enumerate(collection)
        )
        return BlockCollection(normalized)

    def normalize_content_fields(
        self,
        data: RevisionData,
        fields: tuple[BlockFieldDefinition, ...],
    ) -> RevisionData:
        """Canonicalize all declared block collections in current content JSON."""
        raw = data.as_dict()
        for field in fields:
            field_path = _json_path(field.path)
            value = _read_path(raw, field.path)
            if value is _MISSING:
                if field.required:
                    raise BlockValidationError(
                        (
                            ValidationIssue(
                                code="block_field_required",
                                message="Required block field is missing.",
                                path=field_path,
                            ),
                        )
                    )
                continue
            collection = BlockCollection.from_json(value)
            normalized = self.normalize_collection(
                collection,
                constraint=field.constraint,
                path=field_path,
            )
            _write_path(raw, field.path, normalized.as_json(), create=False)
        return RevisionData.from_mapping(raw)

    def apply_delivery_fields(
        self,
        *,
        storage_data: RevisionData,
        delivery_data: Mapping[str, object],
        fields: tuple[BlockFieldDefinition, ...],
    ) -> dict[str, object]:
        """Render declared block fields into a content Delivery representation."""
        storage = storage_data.as_dict()
        output = RevisionData.from_mapping(delivery_data).as_dict()
        for field in fields:
            value = _read_path(storage, field.path)
            if value is _MISSING:
                if field.required:
                    raise BlockValidationError(
                        (
                            ValidationIssue(
                                code="block_field_required",
                                message="Required block field is missing.",
                                path=_json_path(field.path),
                            ),
                        )
                    )
                continue
            collection = BlockCollection.from_json(value)
            rendered = self.delivery_collection(
                collection,
                constraint=field.constraint,
                path=_json_path(field.path),
            )
            _write_path(output, field.public_path, rendered, create=True)
        return output

    def delivery_collection(
        self,
        collection: BlockCollection,
        *,
        constraint: BlockListConstraint | None = None,
        path: str = "$",
    ) -> list[object]:
        """Return recursive current Delivery JSON for one block collection."""
        normalized = self.normalize_collection(
            collection,
            constraint=constraint,
            path=path,
        )
        return [
            self._delivery_node(block, path=f"{path}[{index}]")
            for index, block in enumerate(normalized)
        ]

    def _normalize_node(self, block: BlockNode, *, path: str) -> BlockNode:
        entry = self.require(block.type_key)
        try:
            value = entry.definition.decode_untyped(
                schema_version=block.schema_version,
                data=block.data,
            )
        except BlockValidationError as exc:
            raise BlockValidationError(
                tuple(_prefix_issue(issue, f"{path}.data") for issue in exc.issues)
            ) from exc
        encoded = entry.definition.encode_untyped(value)

        declared_slots = {slot.name: slot for slot in entry.definition.slots}
        provided_slots = dict(block.slots)
        unknown_slots = sorted(set(provided_slots) - set(declared_slots))
        if unknown_slots:
            raise BlockValidationError(
                tuple(
                    ValidationIssue(
                        code="unknown_block_slot",
                        message=f"Block type '{block.type_key}' has no slot '{name}'.",
                        path=f"{path}.slots.{name}",
                    )
                    for name in unknown_slots
                )
            )

        normalized_slots = []
        for slot in entry.definition.slots:
            children = provided_slots.get(slot.name, BlockCollection())
            normalized_slots.append(
                (
                    slot.name,
                    self.normalize_collection(
                        children,
                        constraint=slot.constraint,
                        path=f"{path}.slots.{slot.name}",
                    ),
                )
            )

        return BlockNode(
            id=block.id,
            type_key=block.type_key,
            schema_version=encoded.schema_version,
            data=encoded.data,
            slots=tuple(normalized_slots),
        )

    def _delivery_node(
        self,
        block: BlockNode,
        *,
        path: str,
    ) -> dict[str, object]:
        entry = self.require(block.type_key)
        slots = {
            name: [
                self._delivery_node(child, path=f"{path}.slots.{name}[{index}]")
                for index, child in enumerate(collection)
            ]
            for name, collection in block.slots
        }
        return {
            "id": str(block.id),
            "type": str(block.type_key),
            "data": entry.definition.delivery_data(
                schema_version=block.schema_version,
                data=block.data,
            ),
            "slots": slots,
        }


@dataclass(frozen=True, slots=True)
class StrataRegistry:
    """Frozen registry used after startup compilation succeeds."""

    plugins: PluginRegistry
    content_types: ContentTypeRegistry
    blocks: BlockTypeRegistry


class StrataRegistryBuilder:
    """Startup-only mutable builder consumed exactly once by ``build``."""

    def __init__(self) -> None:
        """Initialize empty registration state for a fresh startup builder."""
        self._plugins: dict[PluginKey, PluginDefinition] = {}
        self._content_types: dict[ContentTypeKey, RegisteredContentTypeEntry] = {}
        self._blocks: dict[BlockTypeKey, RegisteredBlockTypeEntry] = {}
        self._consumed = False

    def register_plugin(self, plugin: PluginDefinition) -> None:
        """Register one plugin metadata definition."""
        self._require_open()
        if plugin.key in self._plugins:
            raise DuplicatePluginError(f"Plugin '{plugin.key}' is already registered.")
        self._plugins[plugin.key] = plugin

    def registrar_for(self, owner: PluginKey) -> PluginRegistrar:
        """Return a registration surface permanently scoped to one plugin."""
        self._require_open()
        if owner not in self._plugins:
            raise UnknownPluginOwnerError(
                f"Cannot create registrar for unknown plugin '{owner}'."
            )
        return _ScopedPluginRegistrar(self, owner)

    def _register_content_type(
        self,
        definition: RegisteredContentType,
        *,
        owner: PluginKey,
    ) -> None:
        """Register one owned content type through a scoped registrar."""
        self._require_open()
        if definition.key in self._content_types:
            raise DuplicateContentTypeError(
                f"Content type '{definition.key}' is already registered."
            )
        self._content_types[definition.key] = RegisteredContentTypeEntry(
            owner=owner,
            definition=definition,
        )

    def _register_block_type(
        self,
        definition: RegisteredBlockType,
        *,
        owner: PluginKey,
    ) -> None:
        """Register one owned block type through a scoped registrar."""
        self._require_open()
        if definition.key in self._blocks:
            raise DuplicateBlockTypeError(
                f"Block type '{definition.key}' is already registered."
            )
        self._blocks[definition.key] = RegisteredBlockTypeEntry(
            owner=owner,
            definition=definition,
        )

    def build(
        self,
        *,
        strata_version: str,
        plugin_api_version: int = STRATA_PLUGIN_API_VERSION,
    ) -> StrataRegistry:
        """Validate the full graph, freeze it, and consume this builder."""
        self._require_open()
        ordered_plugins = self._validate_and_order_plugins(
            strata_version=Version(strata_version),
            plugin_api_version=plugin_api_version,
        )
        self._validate_definition_owners()
        self._validate_block_references()
        self._consumed = True
        return StrataRegistry(
            plugins=PluginRegistry(ordered_plugins),
            content_types=ContentTypeRegistry(self._content_types.values()),
            blocks=BlockTypeRegistry(self._blocks.values()),
        )

    def _require_open(self) -> None:
        if self._consumed:
            raise RegistryFrozenError(
                "Registry builder has already been compiled and cannot mutate."
            )

    def _validate_definition_owners(self) -> None:
        for content_entry in self._content_types.values():
            if content_entry.owner not in self._plugins:
                raise UnknownPluginOwnerError(
                    f"Definition is owned by unknown plugin '{content_entry.owner}'."
                )
        for block_entry in self._blocks.values():
            if block_entry.owner not in self._plugins:
                raise UnknownPluginOwnerError(
                    f"Definition is owned by unknown plugin '{block_entry.owner}'."
                )

    def _validate_block_references(self) -> None:
        for block_entry in self._blocks.values():
            for slot in block_entry.definition.slots:
                self._require_known_blocks(
                    slot.constraint,
                    owner=block_entry.owner,
                    context=(
                        f"block '{block_entry.definition.key}' slot '{slot.name}'"
                    ),
                )
        for content_entry in self._content_types.values():
            for field in content_entry.definition.block_fields:
                self._require_known_blocks(
                    field.constraint,
                    owner=content_entry.owner,
                    context=(
                        f"content type '{content_entry.definition.key}' field "
                        f"'{'.'.join(field.path)}'"
                    ),
                )

    def _require_known_blocks(
        self,
        constraint: BlockListConstraint,
        *,
        owner: PluginKey,
        context: str,
    ) -> None:
        allowed = constraint.allowed_types
        if allowed is None:
            return
        unknown = sorted((key for key in allowed if key not in self._blocks), key=str)
        if unknown:
            raise UnknownBlockReferenceError(
                f"{context} references unregistered block type(s): "
                + ", ".join(str(key) for key in unknown)
            )

        dependencies = self._transitive_dependencies(owner)
        undeclared = sorted(
            (
                key
                for key in allowed
                if self._blocks[key].owner != owner
                and self._blocks[key].owner not in dependencies
            ),
            key=str,
        )
        if undeclared:
            referenced_plugins = sorted(
                {self._blocks[key].owner for key in undeclared},
                key=str,
            )
            raise UndeclaredPluginDependencyError(
                f"{context} references blocks owned by undeclared plugin "
                "dependency/dependencies: "
                + ", ".join(str(key) for key in referenced_plugins)
            )

    def _transitive_dependencies(self, owner: PluginKey) -> set[PluginKey]:
        found: set[PluginKey] = set()
        pending = [
            requirement.key for requirement in self._plugins[owner].requires_plugins
        ]
        while pending:
            key = pending.pop()
            if key in found:
                continue
            found.add(key)
            pending.extend(
                requirement.key for requirement in self._plugins[key].requires_plugins
            )
        return found

    def _validate_and_order_plugins(
        self,
        *,
        strata_version: Version,
        plugin_api_version: int,
    ) -> tuple[PluginDefinition, ...]:
        dependents: dict[PluginKey, set[PluginKey]] = defaultdict(set)
        dependency_count: dict[PluginKey, int] = {}

        for plugin in self._plugins.values():
            if plugin.plugin_api_version != plugin_api_version:
                raise UnsupportedPluginAPIVersionError(
                    f"Plugin '{plugin.key}' targets plugin API "
                    f"{plugin.plugin_api_version}, running API is "
                    f"{plugin_api_version}."
                )
            if strata_version not in SpecifierSet(plugin.requires_strata):
                raise IncompatibleCMSVersionError(
                    f"Plugin '{plugin.key}' {plugin.version} requires CMS "
                    f"'{plugin.requires_strata}', running {strata_version}."
                )

            dependency_count[plugin.key] = len(plugin.requires_plugins)
            for requirement in plugin.requires_plugins:
                dependency = self._plugins.get(requirement.key)
                if dependency is None:
                    raise MissingPluginDependencyError(
                        f"Plugin '{plugin.key}' requires missing plugin "
                        f"'{requirement.key}'."
                    )
                if Version(dependency.version) not in SpecifierSet(requirement.version):
                    raise IncompatiblePluginVersionError(
                        f"Plugin '{plugin.key}' requires '{requirement.key}' "
                        f"'{requirement.version}', installed {dependency.version}."
                    )
                dependents[requirement.key].add(plugin.key)

        ready = sorted(
            (key for key, count in dependency_count.items() if count == 0),
            key=str,
        )
        ordered_keys: list[PluginKey] = []
        while ready:
            key = ready.pop(0)
            ordered_keys.append(key)
            for dependent in sorted(dependents[key], key=str):
                dependency_count[dependent] -= 1
                if dependency_count[dependent] == 0:
                    ready.append(dependent)
                    ready.sort(key=str)

        if len(ordered_keys) != len(self._plugins):
            cyclic = sorted(
                (key for key, count in dependency_count.items() if count > 0),
                key=str,
            )
            raise PluginDependencyCycleError(
                "Plugin dependency cycle detected involving: "
                + ", ".join(str(key) for key in cyclic)
            )

        return tuple(self._plugins[key] for key in ordered_keys)


def _read_path(root: Mapping[str, object], path: tuple[str, ...]) -> object:
    current: object = root
    for segment in path:
        if not isinstance(current, Mapping) or segment not in current:
            return _MISSING
        current = current[segment]
    return current


def _write_path(
    root: dict[str, object],
    path: tuple[str, ...],
    value: object,
    *,
    create: bool,
) -> None:
    current = root
    for segment in path[:-1]:
        child = current.get(segment)
        if child is None and create:
            replacement: dict[str, object] = {}
            current[segment] = replacement
            current = replacement
            continue
        if not isinstance(child, dict):
            raise SchemaDecodeError(
                f"Cannot write block field through non-object path {_json_path(path)}."
            )
        current = child
    if not create and path[-1] not in current:
        raise SchemaDecodeError(
            f"Cannot normalize missing block field {_json_path(path)}."
        )
    current[path[-1]] = value


def _json_path(path: tuple[str, ...]) -> str:
    return "$" + "".join(f".{segment}" for segment in path)


def _prefix_issue(issue: ValidationIssue, prefix: str) -> ValidationIssue:
    suffix = issue.path[1:] if issue.path.startswith("$") else f".{issue.path}"
    return ValidationIssue(
        code=issue.code,
        message=issue.message,
        path=prefix + suffix,
    )
