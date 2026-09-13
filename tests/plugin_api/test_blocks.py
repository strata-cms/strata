from dataclasses import dataclass
from uuid import UUID

import pytest

from strata_cms.domain.revision import RevisionData
from strata_cms.examples.simple_article import EXAMPLE_PLUGIN, register_example
from strata_cms.examples.structured_page import (
    LANDING_PAGE_TYPE,
    SECTION_BLOCK_TYPE,
    TEXT_BLOCK,
    TEXT_BLOCK_TYPE,
)
from strata_cms.plugin_api import (
    BlockCollection,
    BlockDefinition,
    BlockListConstraint,
    BlockSchema,
    BlockSlotDefinition,
    BlockTypeKey,
    BlockValidationError,
    DuplicateBlockTypeError,
    InvalidBlockEnvelopeError,
    PluginDefinition,
    PluginKey,
    SchemaMigrationSet,
    StrataRegistryBuilder,
    ValidationIssue,
)
from strata_cms.plugin_api.errors import (
    UndeclaredPluginDependencyError,
    UnknownBlockReferenceError,
)


def _text_block(*, version: int = 2, field: str = "text") -> dict[str, object]:
    return {
        "id": "00000000-0000-0000-0000-000000000101",
        "type": str(TEXT_BLOCK_TYPE),
        "version": version,
        "data": {field: "Hello"},
        "slots": {},
    }


def _section_block(children: list[object]) -> dict[str, object]:
    return {
        "id": "00000000-0000-0000-0000-000000000201",
        "type": str(SECTION_BLOCK_TYPE),
        "version": 1,
        "data": {"variant": "hero"},
        "slots": {"children": children},
    }


def _registry():  # type: ignore[no-untyped-def]
    builder = StrataRegistryBuilder()
    register_example(builder)
    return builder.build(strata_version="0.1.0")


def test_block_collection_round_trips_stable_envelope() -> None:
    collection = BlockCollection.from_json([_text_block()])

    assert collection.as_json() == [_text_block()]
    assert str(collection.blocks[0].id) == "00000000-0000-0000-0000-000000000101"


def test_block_registry_migrates_historical_block_and_preserves_identity() -> None:
    collection = BlockCollection.from_json([_text_block(version=1, field="value")])

    normalized = _registry().blocks.normalize_collection(collection)
    block = normalized.blocks[0]

    assert str(block.id) == "00000000-0000-0000-0000-000000000101"
    assert block.schema_version == 2
    assert block.data.as_dict() == {"text": "Hello"}


def test_nested_slots_are_validated_and_rendered_for_delivery() -> None:
    collection = BlockCollection.from_json([_section_block([_text_block()])])

    rendered = _registry().blocks.delivery_collection(collection)

    assert rendered == [
        {
            "id": "00000000-0000-0000-0000-000000000201",
            "type": str(SECTION_BLOCK_TYPE),
            "data": {"variant": "hero"},
            "slots": {
                "children": [
                    {
                        "id": "00000000-0000-0000-0000-000000000101",
                        "type": str(TEXT_BLOCK_TYPE),
                        "data": {"text": "Hello", "kind": "text"},
                        "slots": {},
                    }
                ]
            },
        }
    ]


def test_slot_rejects_disallowed_child_type() -> None:
    nested_section = _section_block([_section_block([_text_block()])])
    collection = BlockCollection.from_json([nested_section])

    with pytest.raises(BlockValidationError) as raised:
        _registry().blocks.normalize_collection(collection)

    assert raised.value.issues[0].code == "block_type_not_allowed"
    assert ".slots.children[0]" in raised.value.issues[0].path


def test_block_rejects_unknown_slot() -> None:
    raw = _text_block()
    raw["slots"] = {"children": []}
    collection = BlockCollection.from_json([raw])

    with pytest.raises(BlockValidationError) as raised:
        _registry().blocks.normalize_collection(collection)

    assert raised.value.issues[0].code == "unknown_block_slot"


def test_block_parser_limits_nesting_depth() -> None:
    raw: dict[str, object] = _text_block()
    for index in range(34):
        raw = {
            "id": str(UUID(int=1000 + index)),
            "type": str(SECTION_BLOCK_TYPE),
            "version": 1,
            "data": {"variant": "nested"},
            "slots": {"children": [raw]},
        }

    with pytest.raises(InvalidBlockEnvelopeError):
        BlockCollection.from_json([raw])


def test_registry_rejects_duplicate_block_type() -> None:
    builder = StrataRegistryBuilder()
    builder.register_plugin(EXAMPLE_PLUGIN)
    registrar = builder.registrar_for(EXAMPLE_PLUGIN.key)
    registrar.register_block_type(TEXT_BLOCK)

    with pytest.raises(DuplicateBlockTypeError):
        registrar.register_block_type(TEXT_BLOCK)


def test_registry_rejects_unknown_block_reference() -> None:
    @dataclass(frozen=True)
    class ContainerData:
        name: str

    class ContainerSchema(BlockSchema[ContainerData]):
        value_type = ContainerData

        def deserialize(self, data: RevisionData) -> ContainerData:
            return ContainerData(name=str(data.as_dict().get("name", "")))

        def serialize(self, value: ContainerData) -> RevisionData:
            return RevisionData.from_mapping({"name": value.name})

        def validate(self, value: ContainerData) -> tuple[ValidationIssue, ...]:
            del value
            return ()

    block = BlockDefinition(
        key=BlockTypeKey("tests.container"),
        schema_version=1,
        schema=ContainerSchema(),
        migrations=SchemaMigrationSet(),
        slots=(
            BlockSlotDefinition(
                "children",
                BlockListConstraint(
                    allowed_types=frozenset({BlockTypeKey("tests.missing")})
                ),
            ),
        ),
    )
    plugin = PluginDefinition(
        key=PluginKey("tests.blocks"),
        version="1.0.0",
        requires_strata=">=0.1,<0.2",
    )
    builder = StrataRegistryBuilder()
    builder.register_plugin(plugin)
    builder.registrar_for(plugin.key).register_block_type(block)

    with pytest.raises(UnknownBlockReferenceError):
        builder.build(strata_version="0.1.0")


def test_example_landing_page_declares_registered_block_field() -> None:
    registry = _registry()
    entry = registry.content_types.require(LANDING_PAGE_TYPE)

    assert entry.definition.block_fields[0].path == ("body",)
    assert set(entry.definition.block_fields[0].constraint.allowed_types or ()) == {
        TEXT_BLOCK_TYPE,
        SECTION_BLOCK_TYPE,
    }


def test_cross_plugin_block_reference_requires_declared_dependency() -> None:
    blocks_plugin = PluginDefinition(
        key=PluginKey("tests.shared_blocks"),
        version="1.0.0",
        requires_strata=">=0.1,<0.2",
    )
    consumer_plugin = PluginDefinition(
        key=PluginKey("tests.consumer"),
        version="1.0.0",
        requires_strata=">=0.1,<0.2",
    )
    builder = StrataRegistryBuilder()
    builder.register_plugin(blocks_plugin)
    builder.register_plugin(consumer_plugin)
    builder.registrar_for(blocks_plugin.key).register_block_type(TEXT_BLOCK)

    @dataclass(frozen=True)
    class ContainerData:
        name: str

    class ContainerSchema(BlockSchema[ContainerData]):
        value_type = ContainerData

        def deserialize(self, data: RevisionData) -> ContainerData:
            return ContainerData(name=str(data.as_dict().get("name", "")))

        def serialize(self, value: ContainerData) -> RevisionData:
            return RevisionData.from_mapping({"name": value.name})

        def validate(self, value: ContainerData) -> tuple[ValidationIssue, ...]:
            del value
            return ()

    container = BlockDefinition(
        key=BlockTypeKey("tests.consumer_container"),
        schema_version=1,
        schema=ContainerSchema(),
        slots=(
            BlockSlotDefinition(
                "children",
                BlockListConstraint(allowed_types=frozenset({TEXT_BLOCK_TYPE})),
            ),
        ),
    )
    builder.registrar_for(consumer_plugin.key).register_block_type(container)

    with pytest.raises(UndeclaredPluginDependencyError):
        builder.build(strata_version="0.1.0")
