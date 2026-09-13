"""Translate the compiled plugin registry into application editor DTOs."""

from collections import deque

from strata_cms.application.editor_models import (
    BlockCollectionEditorFieldSpec,
    BlockConstraintSpec,
    BlockSlotEditorSpec,
    BlockTypeEditorSpec,
    ContentTypeEditorSpec,
    ContentTypeEditorSummary,
    EditorChoiceSpec,
    ScalarEditorFieldSpec,
)
from strata_cms.domain.value_objects import ContentTypeKey
from strata_cms.plugin_api.blocks import (
    BlockFieldDefinition,
    BlockListConstraint,
    BlockTypeKey,
)
from strata_cms.plugin_api.editor import (
    BlockCollectionEditorField,
    BlockEditorDefinition,
    ScalarEditorField,
)
from strata_cms.plugin_api.registry import RegisteredBlockTypeEntry, StrataRegistry


class RegistryEditorCatalog:
    """Expose registry editor metadata through application-owned DTOs."""

    def __init__(self, registry: StrataRegistry) -> None:
        """Bind the adapter to one frozen plugin registry."""
        self._registry = registry

    def list_content_types(self) -> tuple[ContentTypeEditorSummary, ...]:
        """Return stable summaries for all installed content definitions."""
        summaries = []
        for entry in self._registry.content_types.all():
            editor = entry.definition.editor
            summaries.append(
                ContentTypeEditorSummary(
                    key=str(entry.definition.key),
                    label=(
                        editor.label
                        if editor is not None
                        else str(entry.definition.key)
                    ),
                    description=editor.description if editor is not None else "",
                    icon=editor.icon if editor is not None else "",
                    editable=editor is not None,
                )
            )
        return tuple(summaries)

    def get_content_type(self, key: ContentTypeKey) -> ContentTypeEditorSpec | None:
        """Return a compiled editor contract for one installed content type."""
        entry = self._registry.content_types.get(key)
        if entry is None:
            return None

        definition = entry.definition
        editor = definition.editor
        block_fields = {field.path: field for field in definition.block_fields}
        fields = (
            ()
            if editor is None
            else tuple(
                self._field_spec(item, block_fields=block_fields)
                for item in editor.fields
            )
        )
        blocks = self._reachable_blocks(definition.block_fields)
        capabilities = tuple(
            sorted(str(capability.value) for capability in definition.capabilities)
        )
        return ContentTypeEditorSpec(
            key=str(definition.key),
            label=editor.label if editor is not None else str(definition.key),
            description=editor.description if editor is not None else "",
            icon=editor.icon if editor is not None else "",
            schema_version=definition.schema_version,
            capabilities=capabilities,
            editable=editor is not None,
            fields=fields,
            initial_data=(editor.initial_data.as_dict() if editor is not None else {}),
            blocks=blocks,
        )

    def _field_spec(
        self,
        field: ScalarEditorField | BlockCollectionEditorField,
        *,
        block_fields: dict[tuple[str, ...], BlockFieldDefinition],
    ) -> ScalarEditorFieldSpec | BlockCollectionEditorFieldSpec:
        if isinstance(field, ScalarEditorField):
            return _scalar_spec(field)
        semantic = block_fields[field.path]
        return BlockCollectionEditorFieldSpec(
            path=field.path,
            label=field.label,
            help_text=field.help_text,
            constraint=_constraint_spec(semantic.constraint),
        )

    def _reachable_blocks(
        self,
        fields: tuple[BlockFieldDefinition, ...],
    ) -> tuple[BlockTypeEditorSpec, ...]:
        if not fields:
            return ()

        all_keys = {entry.definition.key for entry in self._registry.blocks.all()}
        pending: deque[BlockTypeKey] = deque()
        for field in fields:
            pending.extend(_constraint_keys(field.constraint, all_keys))

        visited: set[BlockTypeKey] = set()
        entries: list[RegisteredBlockTypeEntry] = []
        while pending:
            key = pending.popleft()
            if key in visited:
                continue
            visited.add(key)
            entry = self._registry.blocks.require(key)
            entries.append(entry)
            for slot in entry.definition.slots:
                pending.extend(_constraint_keys(slot.constraint, all_keys))

        return tuple(
            self._block_spec(entry)
            for entry in sorted(entries, key=lambda item: str(item.definition.key))
        )

    def _block_spec(self, entry: RegisteredBlockTypeEntry) -> BlockTypeEditorSpec:
        definition = entry.definition
        editor: BlockEditorDefinition | None = definition.editor
        slot_metadata = (
            {slot.name: slot for slot in editor.slots} if editor is not None else {}
        )
        slots = []
        for slot in definition.slots:
            presentation = slot_metadata.get(slot.name)
            slots.append(
                BlockSlotEditorSpec(
                    name=slot.name,
                    label=(
                        presentation.label
                        if presentation is not None
                        else slot.name.replace("_", " ").title()
                    ),
                    help_text=(
                        presentation.help_text if presentation is not None else ""
                    ),
                    constraint=_constraint_spec(slot.constraint),
                )
            )

        return BlockTypeEditorSpec(
            key=str(definition.key),
            label=editor.label if editor is not None else str(definition.key),
            description=editor.description if editor is not None else "",
            icon=editor.icon if editor is not None else "",
            schema_version=definition.schema_version,
            editable=editor is not None,
            fields=(
                tuple(_scalar_spec(field) for field in editor.fields)
                if editor is not None
                else ()
            ),
            slots=tuple(slots),
            initial_data=(editor.initial_data.as_dict() if editor is not None else {}),
        )


def _scalar_spec(field: ScalarEditorField) -> ScalarEditorFieldSpec:
    return ScalarEditorFieldSpec(
        path=field.path,
        label=field.label,
        input_kind=field.input_kind.value,
        required=field.required,
        help_text=field.help_text,
        placeholder=field.placeholder,
        read_only=field.read_only,
        choices=tuple(
            EditorChoiceSpec(value=choice.value, label=choice.label)
            for choice in field.choices
        ),
    )


def _constraint_spec(constraint: BlockListConstraint) -> BlockConstraintSpec:
    allowed = constraint.allowed_types
    return BlockConstraintSpec(
        allowed_types=(
            tuple(sorted(str(key) for key in allowed)) if allowed is not None else None
        ),
        min_items=constraint.min_items,
        max_items=constraint.max_items,
    )


def _constraint_keys(
    constraint: BlockListConstraint,
    all_keys: set[BlockTypeKey],
) -> tuple[BlockTypeKey, ...]:
    if constraint.allowed_types is None:
        return tuple(sorted(all_keys, key=str))
    return tuple(sorted(constraint.allowed_types, key=str))
