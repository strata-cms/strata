"""Presentation-neutral editor metadata exposed by content and block plugins."""

import re
from dataclasses import dataclass, field
from enum import StrEnum

from strata_cms.domain.revision import RevisionData
from strata_cms.plugin_api.errors import RegistryConfigurationError

_FIELD_SEGMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_SLOT_NAME = re.compile(r"^[a-z][a-z0-9_]*$")


class EditorInputKind(StrEnum):
    """Small semantic input vocabulary understood by management clients."""

    TEXT = "text"
    TEXTAREA = "textarea"
    SLUG = "slug"
    EMAIL = "email"
    URL = "url"
    INTEGER = "integer"
    DECIMAL = "decimal"
    BOOLEAN = "boolean"
    DATE = "date"
    DATETIME = "datetime"
    CHOICE = "choice"
    MULTI_CHOICE = "multi_choice"


@dataclass(frozen=True, slots=True)
class EditorChoice:
    """Stable machine value and human label for choice-based editors."""

    value: str
    label: str

    def __post_init__(self) -> None:
        """Reject ambiguous or unusable choice definitions."""
        if not self.value:
            raise RegistryConfigurationError("Editor choice values cannot be blank.")
        if not self.label.strip():
            raise RegistryConfigurationError("Editor choice labels cannot be blank.")


@dataclass(frozen=True, slots=True)
class ScalarEditorField:
    """Describe how a scalar/object value is presented for human editing."""

    path: tuple[str, ...]
    label: str
    input_kind: EditorInputKind = EditorInputKind.TEXT
    required: bool = True
    help_text: str = ""
    placeholder: str = ""
    read_only: bool = False
    choices: tuple[EditorChoice, ...] = ()

    def __post_init__(self) -> None:
        """Validate stable JSON paths and choice configuration."""
        _validate_path(self.path)
        if not self.label.strip():
            raise RegistryConfigurationError("Editor field labels cannot be blank.")
        choice_kind = self.input_kind in {
            EditorInputKind.CHOICE,
            EditorInputKind.MULTI_CHOICE,
        }
        if choice_kind != bool(self.choices):
            raise RegistryConfigurationError(
                "Editor choices must be supplied exactly for choice input kinds."
            )
        values = [choice.value for choice in self.choices]
        if len(values) != len(set(values)):
            raise RegistryConfigurationError(
                f"Editor field '{'.'.join(self.path)}' has duplicate choice values."
            )


@dataclass(frozen=True, slots=True)
class BlockCollectionEditorField:
    """Human-facing metadata for a structured block collection field."""

    path: tuple[str, ...]
    label: str
    help_text: str = ""

    def __post_init__(self) -> None:
        """Validate the path without duplicating block semantic constraints."""
        _validate_path(self.path)
        if not self.label.strip():
            raise RegistryConfigurationError("Block editor labels cannot be blank.")


EditorField = ScalarEditorField | BlockCollectionEditorField


@dataclass(frozen=True, slots=True)
class ContentEditorDefinition:
    """Optional human-editing description for one registered content type."""

    label: str
    fields: tuple[EditorField, ...]
    description: str = ""
    icon: str = ""
    initial_data: RevisionData = field(
        default_factory=lambda: RevisionData.from_mapping({})
    )

    def __post_init__(self) -> None:
        """Require one deterministic editor definition per JSON field path."""
        if not self.label.strip():
            raise RegistryConfigurationError("Content editor labels cannot be blank.")
        paths = [item.path for item in self.fields]
        _validate_unique_non_overlapping_paths(
            paths,
            owner=f"Content editor '{self.label}'",
        )


@dataclass(frozen=True, slots=True)
class BlockSlotEditorDefinition:
    """Optional human label/help for one already-declared block slot."""

    name: str
    label: str
    help_text: str = ""

    def __post_init__(self) -> None:
        """Require slot metadata to use the canonical machine slot name."""
        if not _SLOT_NAME.fullmatch(self.name):
            raise RegistryConfigurationError("Invalid block editor slot name.")
        if not self.label.strip():
            raise RegistryConfigurationError(
                "Block slot editor labels cannot be blank."
            )


@dataclass(frozen=True, slots=True)
class BlockEditorDefinition:
    """Optional human-editing description for one structured block type."""

    label: str
    fields: tuple[ScalarEditorField, ...] = ()
    slots: tuple[BlockSlotEditorDefinition, ...] = ()
    description: str = ""
    icon: str = ""
    initial_data: RevisionData = field(
        default_factory=lambda: RevisionData.from_mapping({})
    )

    def __post_init__(self) -> None:
        """Validate unique field paths and slot metadata names."""
        if not self.label.strip():
            raise RegistryConfigurationError("Block editor labels cannot be blank.")
        paths = [item.path for item in self.fields]
        _validate_unique_non_overlapping_paths(
            paths,
            owner=f"Block editor '{self.label}'",
        )
        names = [slot.name for slot in self.slots]
        if len(names) != len(set(names)):
            raise RegistryConfigurationError(
                f"Block editor '{self.label}' declares slot metadata more than once."
            )


def _validate_path(path: tuple[str, ...]) -> None:
    """Validate object-only JSON paths used by the generic editor."""
    if not path or any(not _FIELD_SEGMENT.fullmatch(segment) for segment in path):
        raise RegistryConfigurationError(
            "Editor field paths must contain one or more identifier-like JSON keys."
        )


def _validate_unique_non_overlapping_paths(
    paths: list[tuple[str, ...]],
    *,
    owner: str,
) -> None:
    """Reject duplicate or ancestor/descendant editor fields."""
    if len(paths) != len(set(paths)):
        raise RegistryConfigurationError(
            f"{owner} declares a field path more than once."
        )
    for index, left in enumerate(paths):
        for right in paths[index + 1 :]:
            shortest = min(len(left), len(right))
            if left[:shortest] == right[:shortest]:
                raise RegistryConfigurationError(
                    f"{owner} declares overlapping field paths "
                    f"'{'.'.join(left)}' and '{'.'.join(right)}'."
                )
