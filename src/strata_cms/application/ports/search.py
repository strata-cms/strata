"""Provider-neutral search contracts."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol
from uuid import UUID


class SearchCapability(StrEnum):
    """Optional search features exposed explicitly by a backend."""

    FACETS = "facets"
    FUZZY = "fuzzy"
    HIGHLIGHTING = "highlighting"
    SUGGESTIONS = "suggestions"


@dataclass(frozen=True, slots=True)
class SearchDocument:
    """Backend-neutral representation of a published searchable document."""

    id: UUID
    text: str
    fields: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class SearchQuery:
    """Baseline search request understood by every backend."""

    text: str
    limit: int = 20
    offset: int = 0
    filters: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class SearchHit:
    """One backend-neutral search hit."""

    document_id: UUID
    score: float | None = None
    fields: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class SearchResult:
    """Search results plus total match count."""

    hits: tuple[SearchHit, ...]
    total: int


class SearchBackend(Protocol):
    """Index and query published content without leaking a provider DSL."""

    @property
    def capabilities(self) -> frozenset[SearchCapability]:
        """Return optional capabilities supported by this backend."""
        ...  # pragma: no cover - protocol declaration

    def index(self, document: SearchDocument) -> None:
        """Insert or replace a searchable document."""
        ...  # pragma: no cover - protocol declaration

    def remove(self, document_id: UUID) -> None:
        """Remove a searchable document if present."""
        ...  # pragma: no cover - protocol declaration

    def search(self, query: SearchQuery) -> SearchResult:
        """Execute a baseline search query."""
        ...  # pragma: no cover - protocol declaration
