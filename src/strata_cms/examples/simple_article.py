"""Small example plugin used to prove the public content-type contract."""

from collections.abc import Mapping
from dataclasses import dataclass

from strata_cms.domain.revision import RevisionData
from strata_cms.domain.value_objects import ContentTypeKey
from strata_cms.examples.structured_page import LANDING_PAGE, SECTION_BLOCK, TEXT_BLOCK
from strata_cms.plugin_api import (
    ContentCapability,
    ContentDeliverySerializer,
    ContentEditorDefinition,
    ContentSchema,
    ContentTypeDefinition,
    EditorInputKind,
    PluginDefinition,
    PluginKey,
    ScalarEditorField,
    SchemaDecodeError,
    SchemaMigration,
    SchemaMigrationSet,
    StrataRegistryBuilder,
    ValidationIssue,
)

EXAMPLE_PLUGIN_KEY = PluginKey("strata_examples.simple_article")
EXAMPLE_CONTENT_TYPE = ContentTypeKey("strata_examples.article")


@dataclass(frozen=True, slots=True)
class ArticleData:
    """Typed current-version representation of the example article."""

    title: str
    body: str


class ArticleSchema(ContentSchema[ArticleData]):
    """Current v2 schema for the example article."""

    value_type = ArticleData

    def deserialize(self, data: RevisionData) -> ArticleData:
        """Decode canonical JSON and reject incompatible shapes."""
        raw = data.as_dict()
        title = raw.get("title")
        body = raw.get("body")
        if not isinstance(title, str) or not isinstance(body, str):
            raise SchemaDecodeError("Article requires string title and body fields.")
        return ArticleData(title=title, body=body)

    def serialize(self, value: ArticleData) -> RevisionData:
        """Encode current typed data as canonical revision JSON."""
        return RevisionData.from_mapping({"title": value.title, "body": value.body})

    def validate(self, value: ArticleData) -> tuple[ValidationIssue, ...]:
        """Require a non-empty editorial title."""
        if value.title.strip():
            return ()
        return (
            ValidationIssue(
                code="title_required",
                message="Article title must not be blank.",
                path="$.title",
            ),
        )


class ArticleDelivery(ContentDeliverySerializer[ArticleData]):
    """Example of API output that is independent from stored field names."""

    def serialize(self, value: ArticleData) -> Mapping[str, object]:
        """Expose stable public fields for the Delivery API."""
        return {
            "title": value.title,
            "body": value.body,
            "kind": "article",
        }


def _migrate_v1_to_v2(data: RevisionData) -> RevisionData:
    """Rename historical ``heading`` to the current ``title`` field."""
    raw = data.as_dict()
    heading = raw.pop("heading", None)
    if "title" not in raw and heading is not None:
        raw["title"] = heading
    return RevisionData.from_mapping(raw)


EXAMPLE_PLUGIN = PluginDefinition(
    key=EXAMPLE_PLUGIN_KEY,
    version="1.0.0",
    requires_strata=">=0.1,<0.2",
)

EXAMPLE_ARTICLE = ContentTypeDefinition(
    key=EXAMPLE_CONTENT_TYPE,
    schema_version=2,
    schema=ArticleSchema(),
    migrations=SchemaMigrationSet(
        (
            SchemaMigration(
                from_version=1,
                to_version=2,
                migrate=_migrate_v1_to_v2,
            ),
        )
    ),
    delivery=ArticleDelivery(),
    editor=ContentEditorDefinition(
        label="Article",
        description="Simple article content type used as a plugin example.",
        icon="article",
        initial_data=RevisionData.from_mapping({"title": "", "body": ""}),
        fields=(
            ScalarEditorField(
                path=("title",),
                label="Title",
                input_kind=EditorInputKind.TEXT,
                placeholder="Article title",
            ),
            ScalarEditorField(
                path=("body",),
                label="Body",
                input_kind=EditorInputKind.TEXTAREA,
            ),
        ),
    ),
    capabilities=frozenset(
        {
            ContentCapability.PUBLISHABLE,
            ContentCapability.PREVIEWABLE,
            ContentCapability.SEARCHABLE,
        }
    ),
)


def register_example(builder: StrataRegistryBuilder) -> None:
    """Register example content plus structured block definitions."""
    builder.register_plugin(EXAMPLE_PLUGIN)
    registrar = builder.registrar_for(EXAMPLE_PLUGIN_KEY)
    registrar.register_block_type(TEXT_BLOCK)
    registrar.register_block_type(SECTION_BLOCK)
    registrar.register_content_type(EXAMPLE_ARTICLE)
    registrar.register_content_type(LANDING_PAGE)
