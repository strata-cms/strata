"""Example structured blocks and a block-backed content type."""

from collections.abc import Mapping
from dataclasses import dataclass

from strata_cms.domain.revision import RevisionData
from strata_cms.domain.value_objects import ContentTypeKey
from strata_cms.plugin_api import (
    BlockCollection,
    BlockCollectionEditorField,
    BlockDefinition,
    BlockDeliverySerializer,
    BlockEditorDefinition,
    BlockFieldDefinition,
    BlockListConstraint,
    BlockSchema,
    BlockSlotDefinition,
    BlockSlotEditorDefinition,
    BlockTypeKey,
    ContentCapability,
    ContentDeliverySerializer,
    ContentEditorDefinition,
    ContentSchema,
    ContentTypeDefinition,
    EditorChoice,
    EditorInputKind,
    ScalarEditorField,
    SchemaDecodeError,
    SchemaMigration,
    SchemaMigrationSet,
    ValidationIssue,
)

TEXT_BLOCK_TYPE = BlockTypeKey("strata_examples.text")
SECTION_BLOCK_TYPE = BlockTypeKey("strata_examples.section")
LANDING_PAGE_TYPE = ContentTypeKey("strata_examples.landing_page")


@dataclass(frozen=True, slots=True)
class TextBlockData:
    """Typed current data for a simple text block."""

    text: str


class TextBlockSchema(BlockSchema[TextBlockData]):
    """Current v2 text block schema."""

    value_type = TextBlockData

    def deserialize(self, data: RevisionData) -> TextBlockData:
        """Decode canonical text block data."""
        text = data.as_dict().get("text")
        if not isinstance(text, str):
            raise SchemaDecodeError("Text block requires a string text field.")
        return TextBlockData(text=text)

    def serialize(self, value: TextBlockData) -> RevisionData:
        """Encode canonical text block data."""
        return RevisionData.from_mapping({"text": value.text})

    def validate(self, value: TextBlockData) -> tuple[ValidationIssue, ...]:
        """Allow empty text while retaining a typed string contract."""
        del value
        return ()


class TextBlockDelivery(BlockDeliverySerializer[TextBlockData]):
    """Example block-specific Delivery representation."""

    def serialize(self, value: TextBlockData) -> Mapping[str, object]:
        """Expose text plus an illustrative public discriminator."""
        return {"text": value.text, "kind": "text"}


def _migrate_text_v1_to_v2(data: RevisionData) -> RevisionData:
    """Rename historical ``value`` to current ``text`` deterministically."""
    raw = data.as_dict()
    value = raw.pop("value", None)
    if "text" not in raw and value is not None:
        raw["text"] = value
    return RevisionData.from_mapping(raw)


TEXT_BLOCK = BlockDefinition(
    key=TEXT_BLOCK_TYPE,
    schema_version=2,
    schema=TextBlockSchema(),
    migrations=SchemaMigrationSet((SchemaMigration(1, 2, _migrate_text_v1_to_v2),)),
    delivery=TextBlockDelivery(),
    editor=BlockEditorDefinition(
        label="Text",
        description="A plain text content block.",
        icon="notes",
        initial_data=RevisionData.from_mapping({"text": ""}),
        fields=(
            ScalarEditorField(
                path=("text",),
                label="Text",
                input_kind=EditorInputKind.TEXTAREA,
            ),
        ),
    ),
)


@dataclass(frozen=True, slots=True)
class SectionBlockData:
    """Presentation-neutral metadata for a nested section container."""

    variant: str


class SectionBlockSchema(BlockSchema[SectionBlockData]):
    """Schema for a container block with one named ``children`` slot."""

    value_type = SectionBlockData

    def deserialize(self, data: RevisionData) -> SectionBlockData:
        """Decode section metadata independently from nested child blocks."""
        variant = data.as_dict().get("variant", "default")
        if not isinstance(variant, str):
            raise SchemaDecodeError("Section variant must be a string.")
        return SectionBlockData(variant=variant)

    def serialize(self, value: SectionBlockData) -> RevisionData:
        """Encode section metadata; children live in the block envelope slot."""
        return RevisionData.from_mapping({"variant": value.variant})

    def validate(self, value: SectionBlockData) -> tuple[ValidationIssue, ...]:
        """Require a non-empty stable variant name."""
        if value.variant.strip():
            return ()
        return (
            ValidationIssue(
                code="section_variant_required",
                message="Section variant must not be blank.",
                path="$.variant",
            ),
        )


SECTION_BLOCK = BlockDefinition(
    key=SECTION_BLOCK_TYPE,
    schema_version=1,
    schema=SectionBlockSchema(),
    slots=(
        BlockSlotDefinition(
            name="children",
            constraint=BlockListConstraint(
                allowed_types=frozenset({TEXT_BLOCK_TYPE}),
                min_items=1,
            ),
        ),
    ),
    editor=BlockEditorDefinition(
        label="Section",
        description="Container that groups child blocks.",
        icon="view_agenda",
        initial_data=RevisionData.from_mapping({"variant": "default"}),
        fields=(
            ScalarEditorField(
                path=("variant",),
                label="Variant",
                input_kind=EditorInputKind.CHOICE,
                choices=(
                    EditorChoice(value="default", label="Default"),
                    EditorChoice(value="wide", label="Wide"),
                ),
            ),
        ),
        slots=(
            BlockSlotEditorDefinition(
                name="children",
                label="Children",
                help_text="Blocks rendered inside this section.",
            ),
        ),
    ),
)


@dataclass(frozen=True, slots=True)
class LandingPageData:
    """Typed content with a structured block collection."""

    title: str
    body: BlockCollection


class LandingPageSchema(ContentSchema[LandingPageData]):
    """Content schema whose ``body`` is a generic structured block field."""

    value_type = LandingPageData

    def deserialize(self, data: RevisionData) -> LandingPageData:
        """Decode current content after generic block normalization."""
        raw = data.as_dict()
        title = raw.get("title")
        if not isinstance(title, str):
            raise SchemaDecodeError("Landing page requires a string title.")
        return LandingPageData(
            title=title,
            body=BlockCollection.from_json(raw.get("body")),
        )

    def serialize(self, value: LandingPageData) -> RevisionData:
        """Encode typed content while preserving normalized block envelopes."""
        return RevisionData.from_mapping(
            {
                "title": value.title,
                "body": value.body.as_json(),
            }
        )

    def validate(self, value: LandingPageData) -> tuple[ValidationIssue, ...]:
        """Require a non-empty editorial title."""
        if value.title.strip():
            return ()
        return (
            ValidationIssue(
                code="title_required",
                message="Landing page title must not be blank.",
                path="$.title",
            ),
        )


class LandingPageDelivery(ContentDeliverySerializer[LandingPageData]):
    """Delivery shape whose body is rendered generically by the registry."""

    def serialize(self, value: LandingPageData) -> Mapping[str, object]:
        """Expose the block field at its declared Delivery path."""
        return {
            "title": value.title,
            "body": value.body.as_json(),
            "kind": "landing_page",
        }


LANDING_PAGE = ContentTypeDefinition(
    key=LANDING_PAGE_TYPE,
    schema_version=1,
    schema=LandingPageSchema(),
    delivery=LandingPageDelivery(),
    editor=ContentEditorDefinition(
        label="Landing page",
        description="Example page composed from structured blocks.",
        icon="web",
        initial_data=RevisionData.from_mapping({"title": "", "body": []}),
        fields=(
            ScalarEditorField(
                path=("title",),
                label="Title",
                input_kind=EditorInputKind.TEXT,
            ),
            BlockCollectionEditorField(
                path=("body",),
                label="Body",
                help_text="Add, reorder, and nest page blocks.",
            ),
        ),
    ),
    capabilities=frozenset(
        {
            ContentCapability.PUBLISHABLE,
            ContentCapability.PREVIEWABLE,
        }
    ),
    block_fields=(
        BlockFieldDefinition(
            path=("body",),
            constraint=BlockListConstraint(
                allowed_types=frozenset({TEXT_BLOCK_TYPE, SECTION_BLOCK_TYPE}),
                min_items=1,
            ),
        ),
    ),
)
