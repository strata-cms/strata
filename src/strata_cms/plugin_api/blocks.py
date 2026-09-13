"""Structured, schema-versioned block contracts exposed to Strata plugins."""

import re
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Protocol, Self
from uuid import UUID

from strata_cms.domain.revision import RevisionData
from strata_cms.plugin_api.editor import BlockEditorDefinition
from strata_cms.plugin_api.errors import (
    BlockValidationError,
    InvalidBlockEnvelopeError,
    RegistryConfigurationError,
    SchemaDecodeError,
)
from strata_cms.plugin_api.migrations import SchemaMigrationSet
from strata_cms.plugin_api.schema import ValidationIssue

_BLOCK_KEY = re.compile(r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+$")
_SLOT_NAME = re.compile(r"^[a-z][a-z0-9_]*$")
_FIELD_SEGMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
MAX_BLOCK_NESTING_DEPTH = 32
_MAX_KEY_LENGTH = 200


@dataclass(frozen=True, slots=True, order=True)
class BlockTypeKey:
    """Stable namespaced block identifier persisted in revision JSON."""

    value: str

    def __post_init__(self) -> None:
        """Require a durable import-path-independent identifier."""
        if len(self.value) > _MAX_KEY_LENGTH or not _BLOCK_KEY.fullmatch(self.value):
            raise RegistryConfigurationError(
                "Block type keys must be <= 200 chars and use lowercase "
                "namespaced identifiers such as 'acme_blog.quote'."
            )

    def __str__(self) -> str:
        """Return the persisted string representation."""
        return self.value


@dataclass(frozen=True, slots=True, order=True)
class BlockId:
    """Stable block identity retained across content revisions when edited."""

    value: UUID

    def __str__(self) -> str:
        """Return the canonical UUID representation."""
        return str(self.value)


@dataclass(frozen=True, slots=True)
class BlockListConstraint:
    """Cardinality and type constraints for one ordered collection of blocks."""

    allowed_types: frozenset[BlockTypeKey] | None = None
    min_items: int = 0
    max_items: int | None = None

    def __post_init__(self) -> None:
        """Reject impossible collection constraints at plugin registration."""
        if self.min_items < 0:
            raise RegistryConfigurationError("Block min_items cannot be negative.")
        if self.max_items is not None and self.max_items < self.min_items:
            raise RegistryConfigurationError(
                "Block max_items cannot be smaller than min_items."
            )

    def allows(self, type_key: BlockTypeKey) -> bool:
        """Return whether one block type is accepted by this collection."""
        return self.allowed_types is None or type_key in self.allowed_types


@dataclass(frozen=True, slots=True)
class BlockSlotDefinition:
    """Named nested block collection exposed by one container block."""

    name: str
    constraint: BlockListConstraint = field(default_factory=BlockListConstraint)

    def __post_init__(self) -> None:
        """Require stable machine-readable slot names."""
        if not _SLOT_NAME.fullmatch(self.name):
            raise RegistryConfigurationError(
                "Block slot names must use lowercase letters, digits, and "
                "underscores and start with a letter."
            )


@dataclass(frozen=True, slots=True)
class BlockFieldDefinition:
    """Identify a block collection embedded inside a content revision payload."""

    path: tuple[str, ...]
    constraint: BlockListConstraint = field(default_factory=BlockListConstraint)
    delivery_path: tuple[str, ...] | None = None
    required: bool = True

    def __post_init__(self) -> None:
        """Validate JSON-object-only field paths used by generic block handling."""
        if not self.path or any(
            not _FIELD_SEGMENT.fullmatch(segment) for segment in self.path
        ):
            raise RegistryConfigurationError(
                "Block field paths must contain one or more identifier-like "
                "JSON object keys."
            )
        if self.delivery_path is not None and (
            not self.delivery_path
            or any(
                not _FIELD_SEGMENT.fullmatch(segment) for segment in self.delivery_path
            )
        ):
            raise RegistryConfigurationError(
                "Block delivery paths must contain identifier-like JSON keys."
            )

    @property
    def public_path(self) -> tuple[str, ...]:
        """Return the Delivery API path for the rendered block collection."""
        return self.delivery_path or self.path


class BlockSchema[T](Protocol):
    """Map one block's current JSON data to and from a typed Python value."""

    value_type: type[T]

    def deserialize(self, data: RevisionData) -> T:
        """Decode current-version block data into a typed value."""
        ...  # pragma: no cover - protocol declaration

    def serialize(self, value: T) -> RevisionData:
        """Encode a typed block value as canonical current-version JSON."""
        ...  # pragma: no cover - protocol declaration

    def validate(self, value: T) -> tuple[ValidationIssue, ...]:
        """Return semantic validation problems for one block value."""
        ...  # pragma: no cover - protocol declaration


class BlockDeliverySerializer[T](Protocol):
    """Serialize one typed block's data for the public Delivery API."""

    def serialize(self, value: T) -> Mapping[str, object]:
        """Return JSON-compatible public data for one block."""
        ...  # pragma: no cover - protocol declaration


@dataclass(frozen=True, slots=True)
class EncodedBlockData:
    """Canonical current-version block data emitted by a block definition."""

    schema_version: int
    data: RevisionData


@dataclass(frozen=True, slots=True)
class BlockDefinition[T]:
    """Declarative definition of one structured block type."""

    key: BlockTypeKey
    schema_version: int
    schema: BlockSchema[T]
    migrations: SchemaMigrationSet = field(default_factory=SchemaMigrationSet)
    slots: tuple[BlockSlotDefinition, ...] = ()
    delivery: BlockDeliverySerializer[T] | None = None
    editor: BlockEditorDefinition | None = None

    def __post_init__(self) -> None:
        """Validate migration history and unique slot names at registration."""
        self.migrations.validate_for(self.schema_version)
        names = [slot.name for slot in self.slots]
        if len(names) != len(set(names)):
            raise RegistryConfigurationError(
                f"Block type '{self.key}' declares a slot more than once."
            )
        if self.editor is not None:
            declared = set(names)
            described = {slot.name for slot in self.editor.slots}
            unknown = described - declared
            if unknown:
                raise RegistryConfigurationError(
                    f"Block type '{self.key}' editor describes unknown slot(s): "
                    + ", ".join(sorted(unknown))
                )

    def decode(self, *, schema_version: int, data: RevisionData) -> T:
        """Upgrade, decode, and validate one persisted block payload."""
        migrated = self.migrations.migrate(
            data,
            from_version=schema_version,
            to_version=self.schema_version,
        )
        try:
            value = self.schema.deserialize(migrated)
        except SchemaDecodeError:
            raise
        except (TypeError, ValueError, KeyError) as exc:
            raise SchemaDecodeError(
                f"Could not decode block type '{self.key}'."
            ) from exc
        self._require_valid(value)
        return value

    def decode_untyped(self, *, schema_version: int, data: RevisionData) -> object:
        """Type-erased decoding used by the heterogeneous block registry."""
        return self.decode(schema_version=schema_version, data=data)

    def encode(self, value: T) -> EncodedBlockData:
        """Validate and encode one typed current-version block value."""
        self._require_valid(value)
        return EncodedBlockData(
            schema_version=self.schema_version,
            data=self.schema.serialize(value),
        )

    def encode_untyped(self, value: object) -> EncodedBlockData:
        """Encode a runtime value after checking its registered Python type."""
        if not isinstance(value, self.schema.value_type):
            raise SchemaDecodeError(
                f"Block type '{self.key}' expects "
                f"{self.schema.value_type.__name__}, got {type(value).__name__}."
            )
        return self.encode(value)

    def delivery_data(
        self,
        *,
        schema_version: int,
        data: RevisionData,
    ) -> dict[str, object]:
        """Decode historical data and produce current Delivery API block data."""
        value = self.decode(schema_version=schema_version, data=data)
        if self.delivery is None:
            return self.schema.serialize(value).as_dict()
        return RevisionData.from_mapping(self.delivery.serialize(value)).as_dict()

    def _require_valid(self, value: T) -> None:
        issues = self.schema.validate(value)
        if issues:
            raise BlockValidationError(issues)


@dataclass(frozen=True, slots=True)
class BlockNode:
    """One immutable block envelope stored inside a content revision."""

    id: BlockId
    type_key: BlockTypeKey
    schema_version: int
    data: RevisionData
    slots: tuple[tuple[str, "BlockCollection"], ...] = ()

    def __post_init__(self) -> None:
        """Protect envelope invariants independent of any installed plugin."""
        if self.schema_version < 1:
            raise InvalidBlockEnvelopeError("Block schema version must be positive.")
        names = [name for name, _collection in self.slots]
        if len(names) != len(set(names)):
            raise InvalidBlockEnvelopeError("Block slot names must be unique.")
        if any(not _SLOT_NAME.fullmatch(name) for name in names):
            raise InvalidBlockEnvelopeError("Stored block slot name is invalid.")

    def get_slot(self, name: str) -> "BlockCollection | None":
        """Return one nested collection without exposing mutable mappings."""
        for slot_name, collection in self.slots:
            if slot_name == name:
                return collection
        return None

    def as_json(self) -> dict[str, object]:
        """Return a fresh JSON-compatible persisted envelope."""
        return {
            "id": str(self.id),
            "type": str(self.type_key),
            "version": self.schema_version,
            "data": self.data.as_dict(),
            "slots": {name: collection.as_json() for name, collection in self.slots},
        }

    @classmethod
    def from_json(
        cls,
        value: object,
        *,
        depth: int = 0,
        max_depth: int = MAX_BLOCK_NESTING_DEPTH,
    ) -> Self:
        """Parse and freeze one untrusted persisted block envelope."""
        if depth > max_depth:
            raise InvalidBlockEnvelopeError(
                f"Block nesting exceeds maximum depth {max_depth}."
            )
        if not isinstance(value, dict):
            raise InvalidBlockEnvelopeError("Each block must be a JSON object.")

        allowed = {"id", "type", "version", "data", "slots"}
        unknown = set(value) - allowed
        if unknown:
            raise InvalidBlockEnvelopeError(
                "Block envelope contains unknown fields: " + ", ".join(sorted(unknown))
            )

        raw_id = value.get("id")
        raw_type = value.get("type")
        raw_version = value.get("version")
        raw_data = value.get("data")
        raw_slots = value.get("slots", {})
        if not isinstance(raw_id, str):
            raise InvalidBlockEnvelopeError("Block id must be a UUID string.")
        if not isinstance(raw_type, str):
            raise InvalidBlockEnvelopeError("Block type must be a string.")
        if type(raw_version) is not int or raw_version < 1:
            raise InvalidBlockEnvelopeError("Block version must be a positive integer.")
        if not isinstance(raw_data, dict):
            raise InvalidBlockEnvelopeError("Block data must be a JSON object.")
        if not isinstance(raw_slots, dict):
            raise InvalidBlockEnvelopeError("Block slots must be a JSON object.")

        try:
            block_id = BlockId(UUID(raw_id))
        except ValueError as exc:
            raise InvalidBlockEnvelopeError("Block id must be a valid UUID.") from exc
        try:
            type_key = BlockTypeKey(raw_type)
        except RegistryConfigurationError as exc:
            raise InvalidBlockEnvelopeError(
                "Stored block type key is invalid."
            ) from exc

        slots: list[tuple[str, BlockCollection]] = []
        for name in sorted(raw_slots):
            if not isinstance(name, str) or not _SLOT_NAME.fullmatch(name):
                raise InvalidBlockEnvelopeError("Stored block slot name is invalid.")
            slots.append(
                (
                    name,
                    BlockCollection.from_json(
                        raw_slots[name],
                        depth=depth + 1,
                        max_depth=max_depth,
                    ),
                )
            )

        return cls(
            id=block_id,
            type_key=type_key,
            schema_version=raw_version,
            data=RevisionData.from_mapping(raw_data),
            slots=tuple(slots),
        )


@dataclass(frozen=True, slots=True)
class BlockCollection:
    """Ordered immutable collection of structured blocks."""

    blocks: tuple[BlockNode, ...] = ()

    def __iter__(self) -> Iterator[BlockNode]:
        """Iterate blocks in editorial order."""
        return iter(self.blocks)

    def __len__(self) -> int:
        """Return the number of sibling blocks."""
        return len(self.blocks)

    def as_json(self) -> list[object]:
        """Return a fresh JSON-compatible ordered block list."""
        return [block.as_json() for block in self.blocks]

    @classmethod
    def from_json(
        cls,
        value: object,
        *,
        depth: int = 0,
        max_depth: int = MAX_BLOCK_NESTING_DEPTH,
    ) -> Self:
        """Parse an untrusted JSON array into immutable block envelopes."""
        if not isinstance(value, list):
            raise InvalidBlockEnvelopeError("Block collection must be a JSON array.")
        return cls(
            tuple(
                BlockNode.from_json(
                    item,
                    depth=depth,
                    max_depth=max_depth,
                )
                for item in value
            )
        )


def validate_collection_constraint(
    collection: BlockCollection,
    constraint: BlockListConstraint,
    *,
    path: str,
) -> None:
    """Validate collection cardinality and allowed block types."""
    count = len(collection)
    issues: list[ValidationIssue] = []
    if count < constraint.min_items:
        issues.append(
            ValidationIssue(
                code="block_count_too_small",
                message=(
                    f"Expected at least {constraint.min_items} blocks, got {count}."
                ),
                path=path,
            )
        )
    if constraint.max_items is not None and count > constraint.max_items:
        issues.append(
            ValidationIssue(
                code="block_count_too_large",
                message=f"Expected at most {constraint.max_items} blocks, got {count}.",
                path=path,
            )
        )
    for index, block in enumerate(collection):
        if not constraint.allows(block.type_key):
            issues.append(
                ValidationIssue(
                    code="block_type_not_allowed",
                    message=f"Block type '{block.type_key}' is not allowed here.",
                    path=f"{path}[{index}]",
                )
            )
    if issues:
        raise BlockValidationError(issues)


def block_fields_are_unique(fields: Sequence[BlockFieldDefinition]) -> bool:
    """Return whether storage and Delivery field paths are unambiguous."""
    storage = [field.path for field in fields]
    delivery = [field.public_path for field in fields]
    return len(storage) == len(set(storage)) and len(delivery) == len(set(delivery))
