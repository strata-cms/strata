"""Framework-neutral DTOs returned to management/editor presentation layers."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class EditorChoiceSpec:
    """Serializable choice metadata."""

    value: str
    label: str


@dataclass(frozen=True, slots=True)
class ScalarEditorFieldSpec:
    """Serializable scalar editor field metadata."""

    path: tuple[str, ...]
    label: str
    input_kind: str
    required: bool
    help_text: str
    placeholder: str
    read_only: bool
    choices: tuple[EditorChoiceSpec, ...] = ()


@dataclass(frozen=True, slots=True)
class BlockConstraintSpec:
    """Serializable constraints for one ordered block collection."""

    allowed_types: tuple[str, ...] | None
    min_items: int
    max_items: int | None


@dataclass(frozen=True, slots=True)
class BlockCollectionEditorFieldSpec:
    """Serializable metadata for a content-level block collection."""

    path: tuple[str, ...]
    label: str
    help_text: str
    constraint: BlockConstraintSpec


EditorFieldSpec = ScalarEditorFieldSpec | BlockCollectionEditorFieldSpec


@dataclass(frozen=True, slots=True)
class BlockSlotEditorSpec:
    """Serializable slot metadata plus semantic child constraints."""

    name: str
    label: str
    help_text: str
    constraint: BlockConstraintSpec


@dataclass(frozen=True, slots=True)
class BlockTypeEditorSpec:
    """Management description of one block type reachable by the content editor."""

    key: str
    label: str
    description: str
    icon: str
    schema_version: int
    editable: bool
    fields: tuple[ScalarEditorFieldSpec, ...]
    slots: tuple[BlockSlotEditorSpec, ...]
    initial_data: dict[str, object]


@dataclass(frozen=True, slots=True)
class ContentTypeEditorSpec:
    """Complete management/editor contract for one content type."""

    key: str
    label: str
    description: str
    icon: str
    schema_version: int
    capabilities: tuple[str, ...]
    editable: bool
    fields: tuple[EditorFieldSpec, ...]
    initial_data: dict[str, object]
    blocks: tuple[BlockTypeEditorSpec, ...]


@dataclass(frozen=True, slots=True)
class ContentTypeEditorSummary:
    """Small content-type descriptor used by editor type choosers."""

    key: str
    label: str
    description: str
    icon: str
    editable: bool
