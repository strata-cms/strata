"""Typed content-schema contracts exposed to Strata plugins."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol

from strata_cms.domain.revision import RevisionData


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    """One stable machine-readable content validation problem."""

    code: str
    message: str
    path: str = "$"


class ContentSchema[T](Protocol):
    """Map immutable JSON snapshots to and from one typed content value."""

    value_type: type[T]

    def deserialize(self, data: RevisionData) -> T:
        """Decode current-version JSON into a typed value."""
        ...  # pragma: no cover - protocol declaration

    def serialize(self, value: T) -> RevisionData:
        """Encode a typed value as canonical current-version JSON."""
        ...  # pragma: no cover - protocol declaration

    def validate(self, value: T) -> tuple[ValidationIssue, ...]:
        """Return semantic validation problems for a decoded value."""
        ...  # pragma: no cover - protocol declaration


class ContentDeliverySerializer[T](Protocol):
    """Serialize typed content into its default Delivery API representation."""

    def serialize(self, value: T) -> Mapping[str, object]:
        """Return JSON-compatible public delivery data."""
        ...  # pragma: no cover - protocol declaration
