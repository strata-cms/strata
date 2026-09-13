"""Immutable content revision snapshot."""

import json
import math
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Self

from strata_cms.domain.errors import InvalidRevisionDataError, InvalidRevisionError
from strata_cms.domain.value_objects import (
    ActorId,
    ContentId,
    ContentTypeKey,
    RevisionId,
)


def _validate_json_value(value: object, *, path: str) -> None:
    """Reject values that are not portable strict JSON."""
    if value is None or isinstance(value, (str, bool, int)):
        return

    if isinstance(value, float):
        if not math.isfinite(value):
            raise InvalidRevisionDataError(f"Non-finite number at {path}.")
        return

    if isinstance(value, list):
        for index, item in enumerate(value):
            _validate_json_value(item, path=f"{path}[{index}]")
        return

    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise InvalidRevisionDataError(
                    f"Object key at {path} must be a string."
                )
            _validate_json_value(item, path=f"{path}.{key}")
        return

    raise InvalidRevisionDataError(
        f"Unsupported revision value at {path}: {type(value).__name__}."
    )


@dataclass(frozen=True, slots=True)
class RevisionData:
    """Canonical immutable JSON object used by persisted revision snapshots."""

    _canonical_json: str

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> Self:
        """Validate and freeze a mapping as canonical strict JSON."""
        materialized = dict(value)
        _validate_json_value(materialized, path="$")
        canonical = json.dumps(
            materialized,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        return cls(canonical)

    def as_dict(self) -> dict[str, object]:
        """Return a fresh mutable JSON object for a persistence/API boundary."""
        decoded = json.loads(self._canonical_json)
        if not isinstance(decoded, dict):  # pragma: no cover - constructor invariant
            raise InvalidRevisionDataError("Revision root must remain a JSON object.")
        return decoded


@dataclass(frozen=True, slots=True)
class Revision:
    """An immutable, schema-versioned snapshot of one content item."""

    id: RevisionId
    content_id: ContentId
    number: int
    content_type: ContentTypeKey
    schema_version: int
    data: RevisionData
    created_at: datetime
    created_by: ActorId

    def __post_init__(self) -> None:
        """Validate immutable revision metadata."""
        if self.number < 1:
            raise InvalidRevisionError("Revision number must be positive.")
        if self.schema_version < 1:
            raise InvalidRevisionError("Revision schema version must be positive.")
        if self.created_at.tzinfo is None or self.created_at.utcoffset() is None:
            raise InvalidRevisionError("Revision timestamps must be timezone-aware.")
