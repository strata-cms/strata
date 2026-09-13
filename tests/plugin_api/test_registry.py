from dataclasses import dataclass

import pytest

from strata_cms.domain.revision import RevisionData
from strata_cms.domain.value_objects import ContentTypeKey
from strata_cms.examples.simple_article import (
    EXAMPLE_ARTICLE,
    EXAMPLE_CONTENT_TYPE,
    EXAMPLE_PLUGIN,
    ArticleData,
    register_example,
)
from strata_cms.plugin_api import (
    ContentTypeDefinition,
    ContentValidationError,
    InvalidSchemaMigrationError,
    PluginDefinition,
    PluginKey,
    PluginRequirement,
    SchemaMigration,
    SchemaMigrationSet,
    StrataRegistryBuilder,
)
from strata_cms.plugin_api.errors import (
    ContentTypeNotFoundError,
    DuplicateContentTypeError,
    DuplicatePluginError,
    IncompatibleCMSVersionError,
    IncompatiblePluginVersionError,
    MissingPluginDependencyError,
    PluginDependencyCycleError,
    RegistryConfigurationError,
    RegistryFrozenError,
    UnknownPluginOwnerError,
    UnsupportedPluginAPIVersionError,
    UnsupportedSchemaVersionError,
)
from strata_cms.plugin_api.schema import ContentSchema, ValidationIssue


def _plugin(
    key: str,
    *,
    version: str = "1.0.0",
    requires: tuple[PluginRequirement, ...] = (),
    requires_strata: str = ">=0.1,<0.2",
    api_version: int = 1,
) -> PluginDefinition:
    return PluginDefinition(
        key=PluginKey(key),
        version=version,
        requires_strata=requires_strata,
        requires_plugins=requires,
        plugin_api_version=api_version,
    )


def test_example_migrates_v1_to_current_typed_value() -> None:
    value = EXAMPLE_ARTICLE.decode(
        schema_version=1,
        data=RevisionData.from_mapping({"heading": "Historical", "body": "Body"}),
    )

    assert value == ArticleData(title="Historical", body="Body")


def test_example_delivery_serializes_current_shape_after_migration() -> None:
    payload = EXAMPLE_ARTICLE.delivery_data(
        schema_version=1,
        data=RevisionData.from_mapping({"heading": "Historical", "body": "Body"}),
    )

    assert payload == {
        "title": "Historical",
        "body": "Body",
        "kind": "article",
    }


def test_example_rejects_semantically_invalid_content() -> None:
    with pytest.raises(ContentValidationError):
        EXAMPLE_ARTICLE.decode(
            schema_version=2,
            data=RevisionData.from_mapping({"title": "  ", "body": "Body"}),
        )


def test_content_type_rejects_future_schema_version() -> None:
    with pytest.raises(UnsupportedSchemaVersionError):
        EXAMPLE_ARTICLE.decode(
            schema_version=3,
            data=RevisionData.from_mapping({"title": "Future", "body": "Body"}),
        )


def test_registry_is_dependency_ordered_and_immutable_after_build() -> None:
    core = _plugin("tests.core")
    extension = _plugin(
        "tests.extension",
        requires=(PluginRequirement(core.key, ">=1,<2"),),
    )
    builder = StrataRegistryBuilder()
    builder.register_plugin(extension)
    builder.register_plugin(core)

    registry = builder.build(strata_version="0.1.0")

    assert [str(plugin.key) for plugin in registry.plugins.all()] == [
        "tests.core",
        "tests.extension",
    ]
    with pytest.raises(RegistryFrozenError):
        builder.register_plugin(_plugin("tests.late"))


def test_registry_exposes_content_owner_and_stable_lookup() -> None:
    builder = StrataRegistryBuilder()
    register_example(builder)

    registry = builder.build(strata_version="0.1.0")
    entry = registry.content_types.require(EXAMPLE_CONTENT_TYPE)

    assert entry.owner == EXAMPLE_PLUGIN.key
    assert entry.definition is EXAMPLE_ARTICLE


def test_registry_rejects_unknown_content_type() -> None:
    builder = StrataRegistryBuilder()
    register_example(builder)
    registry = builder.build(strata_version="0.1.0")

    with pytest.raises(ContentTypeNotFoundError):
        registry.content_types.require(ContentTypeKey("tests.unknown"))


def test_registry_rejects_duplicate_plugin_key() -> None:
    builder = StrataRegistryBuilder()
    plugin = _plugin("tests.plugin")
    builder.register_plugin(plugin)

    with pytest.raises(DuplicatePluginError):
        builder.register_plugin(plugin)


def test_registry_rejects_duplicate_content_type_key() -> None:
    builder = StrataRegistryBuilder()
    builder.register_plugin(EXAMPLE_PLUGIN)
    registrar = builder.registrar_for(EXAMPLE_PLUGIN.key)
    registrar.register_content_type(EXAMPLE_ARTICLE)

    with pytest.raises(DuplicateContentTypeError):
        registrar.register_content_type(EXAMPLE_ARTICLE)


def test_registry_rejects_missing_plugin_dependency() -> None:
    builder = StrataRegistryBuilder()
    builder.register_plugin(
        _plugin(
            "tests.extension",
            requires=(PluginRequirement(PluginKey("tests.missing")),),
        )
    )

    with pytest.raises(MissingPluginDependencyError):
        builder.build(strata_version="0.1.0")


def test_registry_rejects_incompatible_plugin_dependency() -> None:
    core = _plugin("tests.core", version="1.0.0")
    extension = _plugin(
        "tests.extension",
        requires=(PluginRequirement(core.key, ">=2"),),
    )
    builder = StrataRegistryBuilder()
    builder.register_plugin(core)
    builder.register_plugin(extension)

    with pytest.raises(IncompatiblePluginVersionError):
        builder.build(strata_version="0.1.0")


def test_registry_rejects_circular_plugin_dependencies() -> None:
    first_key = PluginKey("tests.first")
    second_key = PluginKey("tests.second")
    builder = StrataRegistryBuilder()
    builder.register_plugin(
        _plugin(
            str(first_key),
            requires=(PluginRequirement(second_key),),
        )
    )
    builder.register_plugin(
        _plugin(
            str(second_key),
            requires=(PluginRequirement(first_key),),
        )
    )

    with pytest.raises(PluginDependencyCycleError):
        builder.build(strata_version="0.1.0")


def test_registry_rejects_incompatible_strata_version() -> None:
    builder = StrataRegistryBuilder()
    builder.register_plugin(_plugin("tests.future", requires_strata=">=9"))

    with pytest.raises(IncompatibleCMSVersionError):
        builder.build(strata_version="0.1.0")


def test_registry_rejects_unsupported_plugin_api() -> None:
    builder = StrataRegistryBuilder()
    builder.register_plugin(_plugin("tests.future", api_version=2))

    with pytest.raises(UnsupportedPluginAPIVersionError):
        builder.build(strata_version="0.1.0")


def test_content_type_requires_complete_migration_chain() -> None:
    @dataclass(frozen=True)
    class Value:
        name: str

    class Schema(ContentSchema[Value]):
        value_type = Value

        def deserialize(self, data: RevisionData) -> Value:
            return Value(str(data.as_dict()["name"]))

        def serialize(self, value: Value) -> RevisionData:
            return RevisionData.from_mapping({"name": value.name})

        def validate(self, value: Value) -> tuple[ValidationIssue, ...]:
            del value
            return ()

    def migrate(data: RevisionData) -> RevisionData:
        return data

    with pytest.raises(InvalidSchemaMigrationError):
        ContentTypeDefinition(
            key=ContentTypeKey("tests.value"),
            schema_version=3,
            schema=Schema(),
            migrations=SchemaMigrationSet((SchemaMigration(1, 2, migrate),)),
        )


def test_registrar_is_scoped_to_registered_plugin_and_freezes_with_builder() -> None:
    builder = StrataRegistryBuilder()
    builder.register_plugin(EXAMPLE_PLUGIN)
    registrar = builder.registrar_for(EXAMPLE_PLUGIN.key)
    registrar.register_content_type(EXAMPLE_ARTICLE)
    builder.build(strata_version="0.1.0")

    with pytest.raises(RegistryFrozenError):
        registrar.register_content_type(EXAMPLE_ARTICLE)


def test_registrar_rejects_unknown_owner() -> None:
    builder = StrataRegistryBuilder()

    with pytest.raises(UnknownPluginOwnerError):
        builder.registrar_for(PluginKey("tests.unknown"))


def test_plugin_rejects_duplicate_dependency_declarations() -> None:
    dependency = PluginKey("tests.core")

    with pytest.raises(RegistryConfigurationError):
        _plugin(
            "tests.extension",
            requires=(
                PluginRequirement(dependency, ">=1"),
                PluginRequirement(dependency, "<2"),
            ),
        )
